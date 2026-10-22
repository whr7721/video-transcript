import asyncio
import hashlib
import json
import queue
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
import local_files as files
import local_media
import media_buffer
import store


class FileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples=tempfile.TemporaryDirectory()
        cls.root=Path(cls.samples.name)
        sample=store.ROOT/'models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/test_wavs/zh.wav'
        if not sample.is_file():
            sample=next((store.ROOT/'models').rglob('zh.wav'))
        for ext in ('wav','flac','mp3','m4a','mp4','mov'):
            cmd=['ffmpeg','-nostdin','-v','error','-y','-i',str(sample),'-ac','1','-ar','16000']
            if ext in {'m4a','mp4','mov'}:cmd+=['-c:a','aac']
            subprocess.run(cmd+[str(cls.root/f'speech.{ext}')],check=True,capture_output=True)

    @classmethod
    def tearDownClass(cls):cls.samples.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',self.data),patch.object(store,'DB',self.data/'tasks.sqlite3'),
                      patch.object(files,'TASKS',queue.Queue()),patch.object(files,'ACTIVE',{}),
                      patch.object(files,'UPLOAD_SLOT',threading.Lock())]
        for p in self.patches:p.start()
        store.init();files.init();files.STOP.clear()
        self.app=FastAPI();self.app.include_router(files.router);self.client=TestClient(self.app)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def create(self,name='speech.wav',size=None):
        response=self.client.post('/api/files/uploads',json={'filename':name,'size_bytes':size})
        self.assertEqual(response.status_code,201,response.text)
        return response.json()['upload_id']

    def upload(self,name='speech.wav',content=None):
        content=content if content is not None else (self.root/name).read_bytes()
        ident=self.create(name,len(content))
        response=self.client.put('/api/files/uploads/'+ident,content=content)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_six_formats_real_probe_decode_and_first_track(self):
        for ext in ('wav','flac','mp3','m4a','mp4','mov'):
            with self.subTest(ext=ext):
                result=self.upload('speech.'+ext)
                task=store.get(result['id']);path=files.directory(task['id'])
                updates=[]
                with patch('transcribe.local_transcribe',return_value={'text':'测试语音','segments':[]}):
                    files.run_task(task,lambda **v:updates.append(v))
                self.assertEqual(updates[-1]['status'],'completed')
                self.assertGreater(local_media.cached_audio(path/'audio.wav'),1)
                self.assertNotIn('source_url',updates[-1]['result'])
                self.assertEqual(media_buffer.public()['reserved_bytes'],0)

    def test_same_bytes_new_name_reuse_preserves_result_and_same_name_new_bytes_distinct(self):
        first=self.upload();task=store.get(first['id']);task.update(status='completed',result={'text':'原稿不可改'})
        info=task['media_info'];path=files.directory(task['id'])
        local_media.prepare(path/'original.media',path/'audio.wav',info)
        store.save(task);before=store.get(task['id'])
        second=self.upload('renamed.wav',(self.root/'speech.wav').read_bytes())
        self.assertEqual(first['id'],second['id']);self.assertTrue(second['cached'])
        self.assertEqual(store.get(task['id']),before)
        content=(self.root/'speech.wav').read_bytes()+b'different'
        third=self.upload('speech.wav',content)
        self.assertNotEqual(first['id'],third['id'])

    def test_declared_size_mismatch_empty_and_streamed_limit_cleanup(self):
        for data,headers,size in [(b'',{},None),(b'abc',{'Content-Length':'4'},None),(b'abc',{},4)]:
            ident=self.create(size=size)
            r=self.client.put('/api/files/uploads/'+ident,content=data,headers=headers)
            self.assertEqual(r.status_code,400,r.text)
            self.assertFalse((files.directory(ident)/'original.part').exists())
        ident=self.create()
        with patch.object(local_media,'MAX_BYTES',8):
            r=self.client.put('/api/files/uploads/'+ident,content=b'x'*9)
        self.assertEqual(r.status_code,400)
        self.assertEqual(media_buffer.public()['used_bytes'],0)

    def test_disconnect_after_bytes_removes_temporary_and_releases_upload_slot(self):
        ident=self.create()
        events=iter([{'type':'http.request','body':b'a'*10000,'more_body':True},{'type':'http.disconnect'}])
        async def receive():return next(events)
        request=Request({'type':'http','method':'PUT','headers':[]},receive)
        with self.assertRaises(HTTPException) as caught:asyncio.run(files.receive_upload(ident,request))
        self.assertEqual(caught.exception.status_code,408)
        self.assertFalse((files.directory(ident)/'original.part').exists())
        self.assertEqual(media_buffer.public()['used_bytes'],0)
        self.assertTrue(files.UPLOAD_SLOT.acquire(blocking=False));files.UPLOAD_SLOT.release()

    def test_session_write_error_does_not_leak_upload_slot(self):
        ident=self.create()
        async def receive():return {'type':'http.disconnect'}
        with patch.object(files,'upload_save',side_effect=OSError('test disk failure')):
            with self.assertRaises(OSError):asyncio.run(files.receive_upload(ident,Request({'type':'http','headers':[]},receive)))
        self.assertTrue(files.UPLOAD_SLOT.acquire(blocking=False));files.UPLOAD_SLOT.release()
        self.assertFalse(files.ACTIVE)

    def test_explicit_cancel_protects_external_file_and_blocks_more_writes(self):
        outside=self.data/'user-original.wav';outside.write_bytes(b'never delete')
        ident=self.create();event=threading.Event();files.ACTIVE[ident]=event
        files.write_chunk(ident,event,b'x'*10000,hashlib.sha256(),0)
        self.assertEqual(media_buffer.public()['used_bytes'],10000)
        self.assertEqual(self.client.delete('/api/files/uploads/'+ident).status_code,200)
        with self.assertRaises(InterruptedError):files.write_chunk(ident,event,b'x',hashlib.sha256(),0)
        self.assertEqual(outside.read_bytes(),b'never delete')
        self.assertEqual(media_buffer.public()['used_bytes'],0)

    def test_reject_bad_name_container_no_audio_and_bad_duration(self):
        for name in ('../a.wav','C:\\a.wav','a.m3u8','x\n.wav'):
            self.assertEqual(self.client.post('/api/files/uploads',json={'filename':name}).status_code,400)
        for content in (b'#EXTM3U\nhttps://example.com/file',b'broken', (self.root/'speech.mp3').read_bytes()):
            ident=self.create()
            self.assertEqual(self.client.put('/api/files/uploads/'+ident,content=content).status_code,400)
        video=self.root/'no-audio.mp4'
        subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i','color=s=16x16:d=1','-an','-c:v','mpeg4',str(video)],check=True,capture_output=True)
        ident=self.create('no-audio.mp4')
        self.assertEqual(self.client.put('/api/files/uploads/'+ident,content=video.read_bytes()).status_code,400)
        fake=self.root/'bad.wav';fake.write_bytes((self.root/'speech.wav').read_bytes())
        for duration in ('nan','inf','7201','0'):
            result=subprocess.CompletedProcess([],0,json.dumps({'format':{'duration':duration},'streams':[{'codec_type':'audio'}]}).encode())
            with patch('local_media.subprocess.run',return_value=result),self.assertRaises(ValueError):local_media.inspect(fake,'bad.wav')

    def test_quota_reservation_is_consumed_once_and_released_on_error(self):
        ident='a'*16;path=files.directory(ident);path.mkdir(parents=True);media_buffer.register(ident)
        with patch.object(media_buffer,'CAPACITY',100):
            with media_buffer.reserve(ident,80):
                self.assertEqual(media_buffer.public()['reserved_bytes'],80)
                (path/'audio.partial.wav').write_bytes(b'a'*30)
                self.assertEqual(media_buffer.public()['reserved_bytes'],50)
                with self.assertRaises(media_buffer.BufferFull):media_buffer.ensure_space(21)
                media_buffer.ensure_space(20)
            self.assertEqual(media_buffer.public()['reserved_bytes'],0)

    def test_decode_does_not_silently_truncate_dishonest_duration(self):
        source=self.root/'speech.wav'
        with self.assertRaises(ValueError):
            local_media.prepare(source,self.data/'audio.wav',{'container':'wav','duration':1})
        self.assertFalse((self.data/'audio.wav').exists())
        self.assertFalse((self.data/'audio.partial.wav').exists())

    def test_full_buffer_evicts_only_confirmed_unpinned_unleased(self):
        for i,state,pinned,leased in [('a','finalized',False,False),('b','awaiting_review',False,False),('c','finalized',True,False),('d','finalized',False,True)]:
            ident=i*16;path=files.directory(ident);path.mkdir(parents=True)
            (path/'original.media').write_bytes(b'x'*25);media_buffer.register(ident,pinned);media_buffer.state(ident,state)
            if leased:media_buffer.touch(ident)
        with patch.object(media_buffer,'CAPACITY',100):
            media_buffer.ensure_space(20)
            self.assertFalse((files.directory('a'*16)/'original.media').exists())
            for i in 'bcd':self.assertTrue((files.directory(i*16)/'original.media').exists())
            with self.assertRaises(media_buffer.BufferFull):media_buffer.ensure_space(30)

    def test_restart_cleans_unfinished_upload_but_keeps_accepted_source(self):
        ident=self.create();files.write_chunk(ident,threading.Event(),b'x'*123,hashlib.sha256(),0)
        result=self.upload();source=files.directory(result['id'])/'original.media'
        original=source.read_bytes()
        with patch.object(files,'worker',return_value=None):files.start();files.stop()
        self.assertFalse((files.directory(ident)/'original.part').exists())
        self.assertEqual(source.read_bytes(),original)
        self.assertEqual(media_buffer.public()['reserved_bytes'],0)

    def test_reimport_evicted_media_prepares_audio_without_rewriting_source_or_editor(self):
        result=self.upload();task=store.get(result['id'])
        task.update(status='completed',result={'text':'原稿必须保留','segments':[]});store.save(task)
        import documents
        original_doc=documents.get(task)
        changed=documents.save(task,original_doc['revision'],{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'人工稿必须保留'}]}]})
        path=files.directory(task['id']);(path/'original.media').unlink()
        restored=self.upload('new-name.wav',(self.root/'speech.wav').read_bytes())
        self.assertTrue(restored['restored'])
        current=store.get(task['id']);updates=[]
        with patch('transcribe.local_transcribe',side_effect=AssertionError('must not transcribe again')):
            files.run_task(current,lambda **v:updates.append(v))
        self.assertFalse(updates[-1]['media_restore_pending'])
        self.assertEqual(store.get(task['id'])['result'],task['result'])
        self.assertEqual(documents.get(task)['content'],changed['content'])
        self.assertEqual(documents.get(task)['revision'],changed['revision'])

    def test_cancel_while_peer_sends_no_more_bytes_releases_request(self):
        ident=self.create()
        async def scenario():
            received=False
            async def receive():
                nonlocal received
                if not received:
                    received=True
                    return {'type':'http.request','body':b'a'*100,'more_body':True}
                await asyncio.sleep(30)
            request=Request({'type':'http','method':'PUT','headers':[]},receive)
            job=asyncio.create_task(files.receive_upload(ident,request))
            for _ in range(100):
                if (files.directory(ident)/'original.part').exists():break
                await asyncio.sleep(.01)
            files.cancel_upload(ident)
            with self.assertRaises(HTTPException):await asyncio.wait_for(job,1)
        asyncio.run(scenario())
        self.assertFalse((files.directory(ident)/'original.part').exists())

    def test_cancel_during_probe_waits_for_handle_then_removes_temporary(self):
        ident=self.create();entered=threading.Event();release=threading.Event()
        def inspect(path,name):
            with path.open('rb'):
                entered.set();release.wait(2)
            return {'container':'wav','duration':1,'audio_tracks':1,'has_video':False}
        async def scenario():
            emitted=False
            async def receive():
                nonlocal emitted
                if not emitted:
                    emitted=True
                    return {'type':'http.request','body':b'a'*100,'more_body':False}
                return {'type':'http.disconnect'}
            job=asyncio.create_task(files.receive_upload(ident,Request({'type':'http','method':'PUT','headers':[]},receive)))
            while not entered.is_set():await asyncio.sleep(.01)
            job.cancel();await asyncio.sleep(.03);release.set()
            with self.assertRaises(asyncio.CancelledError):await job
        with patch('local_media.inspect',side_effect=inspect):asyncio.run(scenario())
        self.assertFalse((files.directory(ident)/'original.part').exists())
        self.assertEqual(store.all_tasks(),[])

    def test_os_instance_lock_rejects_second_process(self):
        import core_instance,sys
        lock=core_instance.acquire(self.data/'.instance.lock')
        try:
            code='import core_instance;from pathlib import Path;core_instance.acquire(Path('+repr(str(self.data/'.instance.lock'))+'))'
            result=subprocess.run([sys.executable,'-c',code],cwd=store.ROOT,capture_output=True)
            self.assertNotEqual(result.returncode,0)
        finally:lock.close()


if __name__=='__main__':unittest.main()
