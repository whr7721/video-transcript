import contextlib,hashlib,io,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import chapter_jobs,chapters,cli_chapters,cli_summary,organizer,shiwen,store

class SkillCLI(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name)
  self.patches=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(cli_summary.settings,'cloud_key',return_value='fixture')]
  for p in self.patches:p.start()
  self.url='https://youtu.be/skill-fixture';self.ident=hashlib.sha256((self.url+'|auto').encode()).hexdigest()[:16];self.directory=self.root/'jobs'/self.ident;self.directory.mkdir(parents=True)
  self.raw={'text':'原始讲话：核心观点。','segments':[{'start':1,'end':3,'text':'原始讲话：核心观点。'}]}
  (self.directory/'transcript.json').write_text(json.dumps(self.raw,ensure_ascii=False),encoding='utf8');self.before=(self.directory/'transcript.json').read_bytes()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def request(self,system,user,max_tokens):
  if system==cli_summary.manuscript.ARTICLE_PROMPT:value={'blocks':[{'kind':'paragraph','text':'完整整理稿'}]}
  elif system==chapter_jobs.PROMPT:
   p=json.loads(user)['core'][0];value={'sections':[{'start_id':p['id'],'title':'核心观点','guide':'交代核心观点。','evidence_id':p['id'],'quote':'原始讲话'}]}
  else:value={'summary':[{'text':'核心观点','source_ids':['seg-0']}],'highlights':[{'text':'亮点','source_ids':['seg-0']}],'tags':['课程'],'questions':['如何应用？'],'terms':[],'quotes':[{'text':'原始讲话','source_ids':['seg-0']}],'root':{'text':'主题','children':[{'text':'要点'}]}}
  return value,{'total_tokens':10}
 def test_json_real_cache_cli_and_chapters(self):
  out,err=io.StringIO(),io.StringIO()
  with patch.object(organizer,'request_json',side_effect=self.request) as model,contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):shiwen.main(['summarize',self.url,'--chapter','--json'])
  v=json.loads(out.getvalue());self.assertEqual(v['id'],self.ident);self.assertIn('完整整理稿',v['summary']);self.assertIn('核心观点',v['chapters']);self.assertIsInstance(v['costDuration'],float);self.assertEqual(model.call_count,3)
  self.assertEqual(self.before,(self.directory/'transcript.json').read_bytes())
  env={**os.environ,'SHIWEN_DATA_DIR':str(self.root),'SILICONFLOW_API_KEY':''}
  r=subprocess.run([sys.executable,'-X','utf8',str(store.ROOT/'shiwen.py'),'summarize',self.url,'--chapter','--json'],cwd=store.ROOT,env=env,capture_output=True,text=True,encoding='utf8',timeout=25)
  self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['id'],self.ident)
  self.assertEqual(self.before,(self.directory/'transcript.json').read_bytes());self.assertTrue((self.directory/'chapters.md').is_file())
 def test_commands_no_ingest_and_add_compatible(self):
  out=io.StringIO()
  with patch.object(shiwen,'add') as add,contextlib.redirect_stdout(out):shiwen.main(['commands']);add.assert_not_called()
  self.assertEqual([r['name'] for r in json.loads(out.getvalue())['commands']],['rewrite','clips','add','summarize','commands'])
  with patch.object(shiwen,'add') as add:shiwen.main(['add',self.url,'--summarize']);self.assertTrue(add.call_args.args[0].summarize)
 def test_failed_json_keeps_stdout_clean_and_original_unchanged(self):
  out,err=io.StringIO(),io.StringIO()
  with patch.object(organizer,'request_json',side_effect=RuntimeError('quota fixture')),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err),self.assertRaises(SystemExit):shiwen.main(['summarize',self.url,'--json'])
  self.assertEqual(out.getvalue(),'');self.assertIn('quota fixture',err.getvalue());self.assertEqual(self.before,(self.directory/'transcript.json').read_bytes())

if __name__=='__main__':unittest.main()
