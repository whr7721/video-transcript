import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app,document_notes as n,store,settings
class NotesTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name)
  self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(settings,'FILE',self.root/'settings.json')]
  for p in self.ps:p.start()
  store.init();self.id='d'*16;self.other='e'*16
  for ident in [self.id,self.other]:store.save({'id':ident,'title':'笔记/课程','status':'completed','created_at':time.time(),'result':{'text':'原始内容','segments':[{'start':5,'end':8,'text':'原始内容'}]}})
  self.c=TestClient(app.app);self.url='/api/document-notes/'+self.id
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def test_notes_anchor_revision_isolation_and_original(self):
  before=store.get(self.id)['result'];r=self.c.post(self.url,json={'text':'重点','block_id':'seg-0'}).json();self.assertEqual(r['timestamp'],5)
  self.assertEqual(len(self.c.get(self.url).json()['notes']),1);self.assertFalse(self.c.get('/api/document-notes/'+self.other).json()['notes'])
  self.assertEqual(self.c.put(self.url+'/'+r['id'],json={'text':'改','revision':0}).status_code,409)
  self.assertEqual(self.c.put(self.url+'/'+r['id'],json={'text':'修改','revision':1}).json()['revision'],2)
  self.assertEqual(self.c.delete(self.url+'/'+r['id']+'?revision=2').status_code,200);self.assertEqual(store.get(self.id)['result'],before)
  self.assertEqual(self.c.post(self.url,json={'text':'坏锚','block_id':'foreign'}).status_code,400)
 def test_obsidian_real_file_and_no_overwrite_external(self):
  self.c.put('/api/document-notes/settings',json={'vaultPath':str(self.root),'filenameTemplate':'{title}-{id}.md'})
  self.c.post(self.url,json={'text':'我的笔记','block_id':'seg-0'})
  r=self.c.post(self.url+'/export/obsidian');self.assertEqual(r.status_code,200);p=Path(r.json()['path']);self.assertIn('我的笔记',p.read_text(encoding='utf8'));self.assertEqual(p.parent,self.root)
  self.assertEqual(self.c.post(self.url+'/export/obsidian').status_code,200)
  p.write_text('用户在Obsidian的修改',encoding='utf8');self.assertEqual(self.c.post(self.url+'/export/obsidian').status_code,409);self.assertEqual(p.read_text(encoding='utf8'),'用户在Obsidian的修改')
  self.assertEqual(self.c.put('/api/document-notes/settings',json={'filenameTemplate':'{title.__class__}'}).status_code,400)
 def test_notion_secret_disabled_and_page_contract(self):
  self.assertEqual(self.c.post(self.url+'/export/notion').status_code,400)
  with patch.object(settings,'protect',side_effect=lambda v,decrypt=False:'encrypted' if not decrypt else 'private-token'):
   r=self.c.put('/api/document-notes/settings',json={'notionParentId':'a'*32,'notionToken':'private-token'});self.assertNotIn('private-token',r.text)
   with patch.object(n,'notion_request',return_value={'id':'page','url':'https://notion.so/page'}) as req:
    a=self.c.post(self.url+'/export/notion').json();b=self.c.post(self.url+'/export/notion').json();self.assertEqual(a,b);self.assertEqual(req.call_count,1)
    payload=req.call_args.args[-1];self.assertEqual(payload['parent'],{'page_id':'a'*32});self.assertIn('children',payload)
  self.assertNotIn('encrypted_notion_token',self.c.get('/api/document-notes/settings').json())

if __name__=='__main__':unittest.main()
