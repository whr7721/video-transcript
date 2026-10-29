import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app,documents,share_snapshot as snap,store
class SnapshotTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name);self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3')]
  for p in self.ps:p.start()
  store.init();self.id='f'*16;store.save({'id':self.id,'title':'<script>alert(1)</script>','url':'javascript:alert(1)','created_at':time.time(),'status':'completed','result':{'text':'原文 <img src=x onerror=alert(1)>','segments':[{'start':3,'end':5,'text':'原文 <img src=x onerror=alert(1)>'}]}});self.c=TestClient(app.app)
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def test_single_file_snapshot_escapes_content_and_inlines_map(self):
  with store.connect() as db:
   documents.init(db);db.execute('INSERT INTO generations VALUES (?,?)',('map',json.dumps({'id':'map','task_id':self.id,'status':'completed','action':'mindmap','mindmap':{'text':'测试主题','children':[{'text':'分支'}]}})))
  before=store.get(self.id)['result'];v=self.c.post('/api/share-snapshots/'+self.id).json();r=self.c.get(v['download']);self.assertEqual(r.status_code,200);s=r.text
  self.assertIn('Markmap.create' if False else 'markmap.Markmap.create',s);self.assertNotIn('<script src=',s);self.assertNotIn('<script>alert(1)',s);self.assertNotIn('href="javascript:',s);self.assertIn('00:00:03',s);self.assertIn('由拾文生成',s);self.assertNotIn('contenteditable',s)
  self.assertEqual(store.get(self.id)['result'],before);self.assertTrue((self.root/'jobs'/self.id/v['filename']).is_file())
 def test_absent_map_does_not_generate_llm(self):
  with patch('organizer.request_json',side_effect=AssertionError('no model')):
   v=self.c.post('/api/share-snapshots/'+self.id).json();self.assertIn('尚无导图',self.c.get(v['download']).text)
  self.assertEqual(self.c.get('/api/share-snapshots/not-valid/download').status_code,404)

if __name__=='__main__':unittest.main()
