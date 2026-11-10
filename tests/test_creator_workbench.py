import importlib.util,json,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import store
SCRIPT=store.ROOT/'skills/creator-workbench/scripts/workbench.py'
spec=importlib.util.spec_from_file_location('creator_workbench',SCRIPT);wb=importlib.util.module_from_spec(spec);spec.loader.exec_module(wb)
class CreatorTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.p=Path(self.tmp.name);self.args=type('A',(),{'directory':str(self.p),'platform':'douyin','images':1,'brief':'测试交付'})();wb.init_job(self.args)
 def tearDown(self):self.tmp.cleanup()
 def ready(self):
  (self.p/'title.txt').write_text('标题',encoding='utf8');(self.p/'正文.md').write_text('正文',encoding='utf8');(self.p/'01.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',1086,1448))
  m=wb.read(self.p/'manifest.json');m.update(images=['01.png'],music={'status':'track_confirmed'},reviews=['已核对正文和图片']);wb.write(self.p/'manifest.json',m);return m
 def test_resume_does_not_overwrite(self):
  with self.assertRaises(ValueError):wb.init_job(self.args)
 def test_pack_exact_allowlist(self):
  self.ready();(self.p/'secret-cookie.txt').write_text('not real');v=wb.pack(self.args)
  import zipfile
  with zipfile.ZipFile(v['zip']) as z:self.assertNotIn('secret-cookie.txt',z.namelist());self.assertIn('01.png',z.namelist())
  self.assertFalse(v['published']);self.assertTrue(v['warnings'])
 def test_missing_file_rejected(self):
  with self.assertRaises(ValueError):wb.pack(self.args)
 def test_review_required(self):
  m=self.ready();m['reviews']=[];wb.write(self.p/'manifest.json',m)
  with self.assertRaises(ValueError):wb.pack(self.args)
 def test_escape_rejected(self):
  m=self.ready();m['images']=['../outside.png'];wb.write(self.p/'manifest.json',m);self.assertTrue(wb.status(self.args)['errors'])
 def test_changed_source_rejected(self):
  m=self.ready();f=self.p/'transcript.json';f.write_text('{}');m['sources']=[{'kind':'source','transcript_path':str(f),'source_hash':'wrong'}];wb.write(self.p/'manifest.json',m);self.assertIn('来源原稿已变化',str(wb.status(self.args)['errors']))
 def test_bad_ratio_rejected(self):
  self.ready();(self.p/'01.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'\0'*8+struct.pack('>II',100,100));self.assertIn('不是3:4',str(wb.status(self.args)['errors']))
 def test_cli_error_nonzero_stdout_clean(self):
  r=subprocess.run([sys.executable,'-X','utf8',str(SCRIPT),'ingest','invalid'],env={**os.environ,'SHIWEN_HOME':str(self.p/'missing')},capture_output=True,text=True,encoding='utf8');self.assertEqual(r.returncode,1);self.assertEqual(r.stdout,'');self.assertIn('error',json.loads(r.stderr))
 def test_ingest_cache_no_text_ai(self):
  import link_ingest,settings,organizer,documents
  root=self.p/'data';root.mkdir();url='https://www.youtube.com/watch?v=cache_test';import hashlib
  ident=hashlib.sha256((url+'|auto').encode()).hexdigest()[:16];folder=root/'jobs'/ident;folder.mkdir(parents=True);wb.write(folder/'transcript.json',{'text':'真实夹具','segments':[{'id':'seg-0','text':'真实夹具'}]})
  args=type('A',(),{'url':url,'episode':None,'output':None})()
  with patch.object(store,'DATA',root),patch.object(store,'DB',root/'tasks.sqlite3'),patch.object(wb,'modules',return_value=(store,link_ingest)),patch.object(organizer,'request_json',side_effect=AssertionError('no text AI')) as llm:
   store.init();v=wb.ingest(args);self.assertTrue(v['cached']);self.assertFalse(v['text_ai_called']);llm.assert_not_called()
if __name__=='__main__':unittest.main()
