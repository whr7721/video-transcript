import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app,document_chat as chat,library,organizer,personal_kb,store

class ChatTests(unittest.TestCase):
 def setUp(self):
  root=Path(__file__).resolve().parents[1]/'runtime';root.mkdir(exist_ok=True);self.tmp=tempfile.TemporaryDirectory(dir=root);path=Path(self.tmp.name)
  self.patches=[patch.object(store,'DATA',path),patch.object(store,'DB',path/'tasks.sqlite3'),patch.object(chat.settings,'cloud_key',return_value='fixture')]
  for p in self.patches:p.start()
  store.init();self.ident='b'*16
  store.save({'id':self.ident,'title':'养花','status':'completed','created_at':time.time(),'result':{'segments':[{'start':10,'end':15,'text':'多肉浇水要先检查土壤，土壤潮湿时不要浇水。'}],'text':'多肉浇水要先检查土壤，土壤潮湿时不要浇水。'}})
  store.save({'id':'c'*16,'title':'外篇','status':'completed','created_at':time.time(),'result':{'text':'火星基地需要特殊材料。'}})
  self.client=TestClient(app.app);self.url='/api/document-chat/'+self.ident
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def answer(self,system,user,max_tokens):
  payload=json.loads(user);self.last=payload;p=payload['original_evidence'][0]
  return {'sections':[{'text':'先检查土壤再决定是否浇水。','citations':[{'id':p['citation_id'],'quote':'多肉浇水要先检查土壤'}]}]}, {'prompt_tokens':20,'completion_tokens':30}
 def ask(self,question='多肉怎么浇水',id='request-fixture-0001',**extra):return self.client.post(self.url,json={'question':question,'id':id,**extra}).json()
 def test_cited_history_idempotency_and_source_bytes(self):
  original=store.get(self.ident)['result']
  with patch.object(organizer,'request_json',side_effect=self.answer) as model:
   v=self.ask();self.assertEqual(v['status'],'completed');ref=v['answer']['sections'][0]['citations'][0];self.assertEqual(ref['start'],10);self.assertEqual(ref['block_id'],'seg-0')
   self.assertEqual(self.ask()['id'],v['id']);self.assertEqual(model.call_count,1)
   self.ask('那为什么',id='request-fixture-0002');self.assertEqual(len(self.last['history']),1)
  self.assertEqual(len(self.client.get(self.url).json()),2);self.assertEqual(store.get(self.ident)['result'],original)
  self.assertEqual(self.client.get('/api/document-chat/'+'c'*16).json(),[])
  self.assertEqual(personal_kb.budget()['calls'],2)
 def test_out_of_document_is_unknown_without_call(self):
  with patch.object(organizer,'request_json') as model:
   v=self.ask('火星基地用什么材料');self.assertTrue(v['answer']['unknown']);model.assert_not_called()
 def test_bad_citation_rejected_and_manual_retry(self):
  with patch.object(organizer,'request_json',return_value=({'sections':[{'text':'假的','citations':[{'id':'foreign','quote':'伪造引文'}]}]},{})) as model:
   self.assertEqual(self.ask()['status'],'failed');self.ask();self.assertEqual(model.call_count,1)
  with patch.object(organizer,'request_json',side_effect=self.answer):self.assertEqual(self.ask(retry=True)['status'],'completed')
 def test_quota_budget_and_interruption_do_not_touch_transcript(self):
  with patch('link_batches.quota',return_value={'remaining':0}),patch.object(organizer,'request_json') as model:
   self.assertEqual(self.ask()['status'],'failed');model.assert_not_called();self.assertEqual(personal_kb.budget()['calls'],0)
  with patch.object(personal_kb,'BUDGET',0),patch.object(organizer,'request_json') as model:
   self.assertEqual(self.ask(id='request-fixture-0002')['status'],'failed');model.assert_not_called()
  chat.save(self.ident,{'id':'interrupted-0001','question':'多肉','status':'running','created_at':1});chat.recover();self.assertEqual(chat.turns(self.ident)[-1]['status'],'failed')
 def test_changed_source_rejects_and_long_context_bounded(self):
  def changed(*args):
   result=self.answer(*args);t=store.get(self.ident);t['result']['text']='原文改变';store.save(t);return result
  with patch.object(organizer,'request_json',side_effect=changed):self.assertEqual(self.ask()['status'],'failed')
  t=store.get(self.ident);t['result']={'text':'原文长材料。'*20000+'最后说明显微镜适合观察细胞。'};store.save(t)
  evidence,payload=chat.context(self.ident,'显微镜观察细胞',[]);self.assertTrue(any('显微镜' in p['text'] for p in evidence));self.assertLessEqual(sum(len(p['text']) for p in evidence),9600);self.assertTrue(all(p['uid']=='audio:'+self.ident for p in evidence))

if __name__=='__main__':unittest.main()
