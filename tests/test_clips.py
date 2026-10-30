import copy,json,subprocess,tempfile,time,unittest,zipfile,io
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app,clips,documents,organizer,store
class ClipTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name)
  self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(clips.settings,'cloud_key',return_value='fixture')]
  for p in self.ps:p.start()
  store.init();self.id='2'*16;self.root.joinpath('jobs',self.id).mkdir(parents=True)
  self.row={'id':self.id,'title':'切片夹具','status':'completed','created_at':time.time(),'result':{'text':'你好，世界。','segments':[{'start':.3,'end':1.3,'text':'你好，世界。','speaker':'说话人1'},{'start':1.5,'end':2.5,'text':'保持好奇。','speaker':'说话人2'}]}}
  store.save(self.row);self.queue=[];self.client=TestClient(app.app)
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def media(self):
  path=self.root/'jobs'/self.id/'audio.wav';subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=3',str(path)],check=True,capture_output=True);return path
 def raw(self):return {'clips':[{'source_ids':['seg-0'],'translations':[{'source_id':'seg-0','en':'Hello, world.'}]}]}
 def selected(self):
  self.media();v=clips.prepare(self.id,1);v.update(clips=clips.validate(self.raw(),v),selected=True);return v
 def test_missing_media_and_time_axis_no_paid_call(self):
  with patch.object(organizer,'request_json') as m:
   self.assertRaisesRegex(ValueError,'没有可用媒体',clips.submit,self.id,1,self.queue.append);self.media();row=copy.deepcopy(self.row);row['result'].pop('segments');store.save(row)
   self.assertRaisesRegex(ValueError,'没有段落时间轴',clips.submit,self.id,1,self.queue.append);m.assert_not_called()
 def test_refs_contiguous_translation_and_buffer(self):
  v=self.selected();r=v['clips'][0];self.assertEqual(r['zh'],'你好，世界。');self.assertEqual(r['start'],0);self.assertAlmostEqual(r['end'],1.6);self.assertEqual(r['speakers'],['说话人1'])
  for bad in [{'clips':[{'source_ids':['seg-99'],'translations':[]}]},{'clips':[{'source_ids':['seg-1','seg-0'],'translations':[]}]},{'clips':[{'source_ids':['seg-0'],'translations':[{'source_id':'seg-1','en':'x'}]}]}]:self.assertRaises(ValueError,clips.validate,bad,v)
 def test_ass_offsets_bilingual_and_escape(self):
  v=self.selected();text=clips.ass(v['clips'][0],clips.STYLE);self.assertIn('0:00:00.30,0:00:01.30',text);self.assertIn('Hello, world.',text);self.assertIn('说话人1',text);self.assertNotIn(r'{\pos',clips.ass_text(r'{\pos(1,2)}'));self.assertIn('ZH',text)
 def test_real_audio_render_cache_and_download(self):
  self.media();original=(self.root/'jobs'/self.id/'audio.wav').read_bytes()
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})) as model:
   result=clips.submit(self.id,1,self.queue.append);self.assertTrue(self.queue[0].startswith('clips:'));done=clips.run(self.queue[0][6:]);self.assertEqual(done['status'],'completed',done)
   result2=clips.submit(self.id,1,self.queue.append);self.assertEqual(result2['status'],'completed');self.assertEqual(model.call_count,1)
  self.assertEqual(original,(self.root/'jobs'/self.id/'audio.wav').read_bytes());self.assertEqual(self.client.get(done['clips'][0]['url']).status_code,200)
  with zipfile.ZipFile(io.BytesIO(self.client.get('/api/clips/'+self.id+'/zip').content)) as z:self.assertTrue(any(n.endswith('.mp4') for n in z.namelist()))
 def test_render_retry_reuses_selection_and_completed(self):
  self.media()
  with patch.object(organizer,'request_json',return_value=(self.raw(),{})) as model,patch.object(clips,'render',side_effect=RuntimeError('fixture')):
   clips.submit(self.id,1,self.queue.append);v=clips.run(self.queue[-1][6:]);self.assertEqual(v['status'],'failed');self.assertEqual(model.call_count,1)
  with patch.object(organizer,'request_json') as model:
   clips.submit(self.id,1,self.queue.append);v=clips.run(self.queue[-1][6:]);self.assertEqual(v['status'],'completed');model.assert_not_called()
 def test_restart_does_not_repeat_paid_and_organizer_ownership(self):
  self.media();v=clips.submit(self.id,1,self.queue.append);job=documents.generation_get(v['id']);job['status']='running';documents.generation_save(job)
  with patch.object(organizer,'request_json') as model:organizer.recover();self.assertEqual(documents.generation_get(v['id'])['status'],'running');clips.recover(self.queue.append);model.assert_not_called()
  self.assertEqual(clips.current(self.id)['status'],'failed');self.assertEqual(len(self.queue),1)
 def test_quota_rejection_and_identity_change(self):
  self.media();v=clips.prepare(self.id,1)
  with patch('link_batches.quota',return_value={'remaining':0}),patch.object(organizer,'request_json') as m:self.assertRaisesRegex(ValueError,'额度',clips.select,v);m.assert_not_called()
  first=v['key'];row=copy.deepcopy(self.row);row['result']['segments'][0]['text']='原文变化';store.save(row);self.assertNotEqual(clips.prepare(self.id,1)['key'],first)
 def test_batch_reference_and_non_media_skip(self):
  import library
  self.media();c=library.create(library.Collection(name='验收合集'));library.replace(c['id'],library.Members(uids=['audio:'+self.id]))
  with patch.object(app.TASKS,'put',side_effect=self.queue.append):
   # Router captures the original bound put, so direct module router for queue test.
   from fastapi import FastAPI
   a=FastAPI();a.include_router(clips.router(self.queue.append));client=TestClient(a);v=client.post('/api/clips/collections/'+c['id'],json={'count':1});self.assertEqual(v.status_code,200,v.text)
   self.assertEqual(len(self.queue),1);self.assertEqual(v.json()['items'][0]['job_id'],clips.current(self.id)['id'])
   self.assertEqual(client.get('/api/clips/collections/'+c['id']+'/preview').json()['requests'],1)
 def test_cli_cached_no_key_and_share_clip_list(self):
  import contextlib,shiwen,share_snapshot
  self.media();v=clips.prepare(self.id,1);v.update(selected=True,clips=clips.validate(self.raw(),v),status='completed');root=clips.folder(self.id)/v['key'];root.mkdir(parents=True);(root/v['clips'][0]['filename']).write_bytes(b'cached');v['clips'][0]['status']='completed';clips.save(v)
  out=io.StringIO()
  with patch.object(organizer,'request_json') as model,contextlib.redirect_stdout(out):shiwen.main(['clips',self.id,'--count','1','--json']);model.assert_not_called()
  self.assertEqual(json.loads(out.getvalue())['status'],'completed')
  with patch.object(organizer,'request_json') as model:
   result=self.client.post('/api/share-snapshots/'+self.id+'?include_clips=true');self.assertEqual(result.status_code,200,result.text);text=self.client.get(result.json()['download']).text;self.assertIn('金句切片清单',text);self.assertIn('Hello, world.',text);model.assert_not_called()
 def test_pending_options_and_missing_manifest_are_safe(self):
  self.media();v=clips.submit(self.id,1,self.queue.append)
  self.assertRaisesRegex(ValueError,'不同选项',clips.submit,self.id,2,self.queue.append)
  (clips.folder(self.id)/v['key']/'manifest.json').unlink();result=clips.run(v['id']);self.assertEqual(result['status'],'failed')

if __name__=='__main__':unittest.main()
