import hashlib
import json
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import documents
import local_files as files
import media_buffer
import podcast_feed
import podcast_text
import podcasts
import store

FEED=b'''<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0"><channel><title>Sample Show</title><item><guid>episode-one</guid><title>First episode</title><enclosure url="https://example.org/audio.wav" type="audio/wav"/><podcast:transcript url="https://example.org/text.txt" type="text/plain"/></item></channel></rss>'''


class PodcastTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'tasks.sqlite3'),
                      patch.object(files,'TASKS',queue.Queue()),patch.object(files,'UPLOAD_SLOT',threading.Lock()),patch.object(podcasts,'EVENTS',{})]
        for p in self.patches:p.start()
        store.init();files.init();podcasts.init();files.STOP.clear()
        self.app=FastAPI();self.app.include_router(podcasts.router);self.client=TestClient(self.app)
        self.calls=[]

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def stream(self,url,consume,limit,**kwargs):
        self.calls.append(url);data=FEED if url.endswith('/feed') else '这是节目提供的全文。\n\n保留自己的疑问，不把故事当作普遍证据。'.encode()
        consume(data);return {'url':url,'bytes':len(data),'content_type':'text/plain'}

    def create(self,mode='text'):
        with patch('article_fetch.stream',side_effect=self.stream):r=self.client.post('/api/podcasts/feeds',json={'url':'https://example.org/feed'})
        self.assertEqual(r.status_code,200,r.text);feed=r.json()
        r=self.client.post('/api/podcasts/imports',json={'feed_id':feed['id'],'episode_id':feed['episodes'][0]['id'],'mode':mode})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()['id']

    def test_preview_does_not_download_audio_or_text(self):
        ident=self.create();self.assertEqual(self.calls,['https://example.org/feed'])
        self.assertEqual(podcasts.status(ident)['status'],'queued');self.assertEqual(store.all_tasks(),[])

    def test_text_pipeline_no_asr_no_fake_time_and_preserves_draft(self):
        ident=self.create()
        with patch('article_fetch.stream',side_effect=self.stream),patch('transcribe.local_transcribe') as asr:
            podcasts.process(ident);asr.assert_not_called()
        state=podcasts.status(ident);self.assertEqual(state['status'],'accepted')
        task=store.get(state['task_id']);self.assertEqual(task['source']['kind'],'podcast')
        self.assertEqual(task['result']['timing_precision'],'none');self.assertNotIn('start',documents.sources(task)[0])
        self.assertFalse(media_buffer.files(task['id']));self.assertEqual(media_buffer.public()['used_bytes'],0)
        raw=task['result'];doc=documents.get(task);doc['content']['content'].append({'type':'paragraph','content':[{'type':'text','text':'My independent note'}]})
        documents.save(task,doc['revision'],doc['content'])
        second=self.create()
        with patch('article_fetch.stream',side_effect=self.stream):podcasts.process(second)
        self.assertEqual(podcasts.status(second)['task_id'],task['id']);self.assertEqual(documents.get(task)['revision'],2)
        self.assertEqual(store.get(task['id'])['result'],raw)

    def test_audio_uses_common_admission_and_local_byte_dedup(self):
        sample=next((store.ROOT/'models').rglob('zh.wav'));data=sample.read_bytes()
        upload=files.create_upload(files.UploadInput(filename='local.wav'))['upload_id'];session=files.upload_get(upload)
        files.write_chunk(upload,threading.Event(),data,hashlib.sha256(),0)
        accepted=files.accept(session,hashlib.sha256(data).hexdigest(),len(data),threading.Event())
        original=store.get(accepted['id']);ident=self.create('audio')
        def audio(url,consume,limit,**kwargs):consume(data);return {'url':url,'bytes':len(data),'content_type':'audio/wav'}
        with patch('article_fetch.stream',side_effect=audio):podcasts.process(ident)
        state=podcasts.status(ident);self.assertEqual(state['status'],'accepted');self.assertEqual(state['task_id'],original['id'])
        self.assertEqual(store.get(original['id']),original)
        with store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM source_associations WHERE task_id=?',(original['id'],)).fetchone()[0],1)

    def test_cancel_during_download_cleans_counted_partial(self):
        ident=self.create('audio')
        def download(url,consume,limit,**kwargs):
            consume(b'partial bytes');podcasts.cancel(ident);consume(b'more')
        original_save=podcasts.save
        def checked_save(table,value):
            if table=='podcast_imports' and value['status']=='cancelled' and value.get('upload_id'):
                self.assertFalse((files.directory(value['upload_id'])/'original.part').exists())
            return original_save(table,value)
        with patch('article_fetch.stream',side_effect=download),patch('podcasts.save',side_effect=checked_save):podcasts.process(ident)
        self.assertEqual(podcasts.status(ident)['status'],'cancelled');self.assertEqual(media_buffer.public()['used_bytes'],0)
        self.assertFalse(files.UPLOAD_SLOT.locked());self.assertEqual(store.all_tasks(),[])

    def test_buffer_pressure_keeps_protected_media_and_releases_slot(self):
        protected='e'*16;files.directory(protected).mkdir(parents=True);(files.directory(protected)/'original.media').write_bytes(b'keep');media_buffer.register(protected)
        ident=self.create('audio')
        with patch.object(media_buffer,'CAPACITY',5),patch('article_fetch.stream',side_effect=self.stream):podcasts.process(ident)
        self.assertEqual(podcasts.status(ident)['status'],'waiting_space');self.assertEqual((files.directory(protected)/'original.media').read_bytes(),b'keep')
        self.assertFalse(files.UPLOAD_SLOT.locked());self.assertEqual(media_buffer.public()['used_bytes'],4)

    def test_queued_cancel_and_restart_do_not_start_network(self):
        ident=self.create();podcasts.cancel(ident)
        with patch('article_fetch.stream') as stream:podcasts.process(ident);podcasts.recover();stream.assert_not_called()
        self.assertEqual(podcasts.status(ident)['status'],'cancelled')

    def test_clean_terminal_upload_is_unchanged_by_restart(self):
        upload=files.create_upload(files.UploadInput(filename='cancelled.mp3'))['upload_id'];files.abort(upload,'cancelled')
        before=files.upload_get(upload)
        with store.connect() as db:buffer_before=tuple(db.execute('SELECT * FROM media_buffer WHERE id=?',(upload,)).fetchone())
        try:files.start()
        finally:files.stop();files.STOP.clear()
        self.assertEqual(files.upload_get(upload),before)
        with store.connect() as db:self.assertEqual(tuple(db.execute('SELECT * FROM media_buffer WHERE id=?',(upload,)).fetchone()),buffer_before)

    def test_admission_wins_even_if_later_association_write_fails(self):
        ident=self.create('audio');data=next((store.ROOT/'models').rglob('zh.wav')).read_bytes()
        def audio(url,consume,limit,**kwargs):consume(data);return {'url':url,'bytes':len(data),'content_type':'audio/wav'}
        with patch('article_fetch.stream',side_effect=audio),patch('podcasts.associate',side_effect=RuntimeError('temporary persistence error')):podcasts.process(ident)
        self.assertEqual(podcasts.status(ident)['status'],'accepted');podcasts.recover()
        with store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM source_associations').fetchone()[0],1)

    def test_namespace_and_stable_identity_on_reordering(self):
        first=podcast_feed.parse(FEED,'https://example.org/feed')
        self.assertEqual(first['episodes'][0]['transcripts'][0]['type'],'text/plain')
        extra=b'<item><title>New</title><enclosure url="https://example.org/new.mp3"/></item>'
        second=podcast_feed.parse(FEED.replace(b'<item>',extra+b'<item>',1),'https://example.org/feed')
        self.assertEqual(first['episodes'][0]['id'],second['episodes'][1]['id'])

    def test_vtt_and_bad_inputs(self):
        result=podcast_text.parse(b'WEBVTT\n\n00:01.000 --> 00:02.000\nhello','text/vtt')
        self.assertEqual(result['segments'][0]['start'],1)
        for data,kind in [(b'<html>captcha</html>','text/plain'),(b'not vtt','text/vtt'),(b'WEBVTT\n\n00:02.000 --> 00:01.000\nwrong','text/vtt')]:
            with self.assertRaises(ValueError):podcast_text.parse(data,kind)

    def test_asr_export_attribution_uses_feed_instead_of_synthetic_filename(self):
        from transcript_stage import finish_transcription
        path=files.directory('f'*16);path.mkdir(parents=True)
        with patch('transcribe.local_transcribe',return_value={'text':'原话','segments':[]}):
            finish_transcription({'id':'f'*16,'provider':'local'},lambda **f:None,path,path/'audio.wav',1,
                                 {'title':'episode','author':'show','source':{'kind':'podcast','feed_url':'https://example.org/feed','original_name':'podcast.mp3'}},time.perf_counter(),True)
        self.assertIn('https://example.org/feed',(path/'transcript.md').read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
