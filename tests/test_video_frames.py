import subprocess,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app,organizer,store,video_frames as f
class Immediate:
 def submit(self,fn,*args):return fn(*args)
class FrameTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name);self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(f.settings,'cloud_key',return_value='fixture'),patch.object(organizer,'EXECUTOR',Immediate())]
  for p in self.ps:p.start()
  store.init();self.id='1'*16;store.save({'id':self.id,'title':'画面夹具','status':'completed','created_at':time.time(),'result':{'text':'原文保持'}})
  self.folder=self.root/'jobs'/self.id;self.folder.mkdir(parents=True);self.c=TestClient(app.app);self.url='/api/video-frames/'+self.id
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def video(self):subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi','-i','color=c=red:s=320x180:r=1:d=2','-c:v','libx264',str(self.folder/'original.mp4')],check=True,capture_output=True,timeout=30)
 def test_audio_unsupported_and_frame_cap(self):
  self.assertFalse(self.c.get(self.url).json()['available']);self.assertEqual(self.c.post(self.url+'/extract',json={}).status_code,400)
  self.assertEqual(self.c.post(self.url+'/extract',json={'max_frames':31}).status_code,422)
 def test_real_frames_cache_resume_and_original(self):
  self.video();before=(self.folder/'original.mp4').read_bytes();r=self.c.post(self.url+'/extract',json={'interval':1,'max_frames':2});self.assertEqual(r.status_code,200,r.text);v=r.json();self.assertEqual(len(v['frames']),2);self.assertEqual(self.c.get(v['frames'][0]['thumbnail']).status_code,200)
  with patch.object(f.vision,'request',side_effect=[({'description':'红色画面','uncertainties':[]},{}),RuntimeError('fixture failure')]) as model:
   self.c.post(self.url+'/describe',json={'indexes':[0,1]});self.assertEqual(model.call_count,2)
  v=self.c.get(self.url).json();self.assertEqual(v['frames'][0]['status'],'completed');self.assertEqual(v['frames'][1]['status'],'failed')
  with patch.object(f.vision,'request',return_value=({'description':'红色画面','uncertainties':[]},{})) as model:
   self.c.post(self.url+'/describe',json={'indexes':[0,1]});self.assertEqual(model.call_count,1)
   self.c.post(self.url+'/describe',json={'indexes':[0,1]});self.assertEqual(model.call_count,1)
  with patch.object(f.subprocess,'run',wraps=f.subprocess.run) as ff:
   self.c.post(self.url+'/extract',json={'interval':1,'max_frames':2});self.assertFalse(any(c.args[0][0]=='ffmpeg' for c in ff.call_args_list))
  self.assertEqual((self.folder/'original.mp4').read_bytes(),before);self.assertEqual(store.get(self.id)['result']['text'],'原文保持')
 def test_quota_reject_and_restart_no_auto_paid(self):
  self.video();self.c.post(self.url+'/extract',json={'interval':1,'max_frames':2})
  with patch('link_batches.quota',return_value={'remaining':0}),patch.object(f.vision,'request') as m:self.assertEqual(self.c.post(self.url+'/describe',json={}).status_code,400);m.assert_not_called()
  v=f.manifest(self.id);v['status']='running';v['frames'][0]['status']='running';f.save(self.id,v);f.recover();self.assertEqual(f.manifest(self.id)['status'],'failed');self.assertEqual(f.manifest(self.id)['frames'][0]['status'],'failed')

if __name__=='__main__':unittest.main()
