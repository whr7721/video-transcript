import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import documents
import media_buffer
import organizer
import manuscript
import store


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'tasks.sqlite3')]
        for p in self.patches:p.start()
        store.init()
        self.task={'id':'eeeeeeeeeeeeeeee','status':'completed','title':'测试','provider':'local','created_at':time.time(),
                   'result':{'text':'第一句。第二句。','segments':[{'text':'第一句。','start':0,'end':3},{'text':'第二句。','start':3,'end':6}]}}
        store.save(self.task)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_save_conflict_versions_and_immutable_source(self):
        doc=documents.get(self.task)
        changed={'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'修改后的稿件'}]}]}
        saved=documents.save(self.task,doc['revision'],changed)
        self.assertEqual(saved['revision'],2)
        with self.assertRaises(documents.Conflict):documents.save(self.task,1,changed)
        self.assertEqual(store.get(self.task['id'])['result']['text'],'第一句。第二句。')
        final=documents.save(self.task,2,changed,True)
        self.assertIsNotNone(final['finalized_at'])
        self.assertEqual(len(final['versions']),3)

    def test_quota_preserves_pending_pinned_and_leased(self):
        for ident in ['pending','finished','pinned','leased']:
            directory=store.DATA/'jobs'/ident;directory.mkdir(parents=True)
            (directory/'original.mp4').write_bytes(b'x'*20)
            media_buffer.register(ident,pinned=ident=='pinned')
            media_buffer.state(ident,'awaiting_review' if ident=='pending' else 'finalized')
        media_buffer.touch('leased')
        with patch.object(media_buffer,'CAPACITY',65):
            media_buffer.ensure_space(0)
            self.assertFalse((store.DATA/'jobs/finished/original.mp4').exists())
            with self.assertRaises(media_buffer.BufferFull):media_buffer.ensure_space(10)
        for ident in ['pending','pinned','leased']:
            self.assertTrue((store.DATA/'jobs'/ident/'original.mp4').exists())

    def test_cleanup_only_owned_and_confirmed(self):
        own=store.DATA/'jobs'/self.task['id'];own.mkdir(parents=True)
        (own/'audio.wav').write_bytes(b'audio')
        historical=store.DATA/'jobs/history';historical.mkdir();(historical/'audio.wav').write_bytes(b'old')
        media_buffer.register(self.task['id'])
        self.assertEqual(media_buffer.cleanup(),0)
        media_buffer.state(self.task['id'],'finalized')
        self.assertEqual(media_buffer.cleanup(),5)
        self.assertTrue((historical/'audio.wav').exists())

    def test_quote_validation_rejects_rewrite_and_fake_source(self):
        value={'items':[{'text':'第一句。','source_ids':['seg-0']},{'text':'伪造金句','source_ids':['seg-0']},{'text':'第二句。','source_ids':['fake']}]}
        good,rejected=organizer.checked_items(value,documents.sources(self.task),'quotes')
        self.assertEqual(len(good),1);self.assertEqual(rejected,2)

    def test_manuscript_preview_preserves_raw_and_draft(self):
        doc=documents.get(self.task)
        job={'id':'test-manuscript','task_id':self.task['id'],'action':'manuscript','base_revision':1}
        answers=[({'blocks':[{'kind':'heading','text':'全文标题'},{'kind':'paragraph','text':'完整整理稿。'}],
                   'uncertainties':[{'original':'第一句','suggestion':'待回听','reason':'测试'},
                                    {'original':'伪造原词','suggestion':'不要收录'}]}, {'total_tokens':10}),
                 ({'blocks':[{'kind':'paragraph','text':'精华回顾。'}]}, {'total_tokens':5})]
        with patch.object(organizer,'request_json',side_effect=answers):
            organizer.run(job,self.task,doc)
        self.assertEqual(job['status'],'completed')
        self.assertEqual(job['total_tokens'],15)
        self.assertEqual(len(job['uncertainties']),1)
        self.assertIn('精华',documents.text(job['essence_content']))
        self.assertEqual(documents.get(self.task)['revision'],1)
        self.assertEqual(store.get(self.task['id'])['result']['text'],'第一句。第二句。')

    def test_manuscript_essence_retry_reuses_full_article(self):
        job={'id':'test-retry','task_id':self.task['id'],'action':'manuscript','base_revision':1}
        with patch.object(organizer,'request_json',side_effect=[({'blocks':[{'kind':'paragraph','text':'已完成全文。'}]},{}),RuntimeError('服务繁忙')]):
            organizer.run(job,self.task,documents.get(self.task))
        self.assertEqual(job['status'],'completed')
        self.assertIn('summary_error',job)
        with patch.object(organizer,'request_json',return_value=({'blocks':[{'kind':'paragraph','text':'重试精华。'}]},{})) as request:
            organizer.run(job,self.task,documents.get(self.task))
        self.assertEqual(request.call_count,1)
        self.assertNotIn('summary_error',job)
        self.assertEqual(documents.text(job['content']),'已完成全文。')

    def test_manuscript_rejects_oversize_without_calling_service(self):
        task={**self.task,'result':{'text':'长'*24001}}
        with patch.object(organizer,'request_json') as request:
            job={'id':'too-long','action':'manuscript'}
            organizer.run(job,task,{})
        self.assertEqual(job['status'],'failed');request.assert_not_called()

    def test_manuscript_nodes_are_plain_safe_and_deduplicated(self):
        value=manuscript.content({'blocks':[{'kind':'paragraph','text':'相同段落'},{'kind':'paragraph','text':'相同段落'}]})
        self.assertEqual(len(value['content']),1)
        for value in [{'blocks':[]},{'blocks':[{'kind':'iframe','text':'bad'}]},
                      {'blocks':[{'kind':'paragraph','text':'<script>alert(1)</script>'}]}]:
            with self.assertRaises(ValueError):manuscript.content(value)

    def test_overlong_essence_preserves_completed_article(self):
        job={'id':'long-essence','task_id':self.task['id'],'action':'manuscript','base_revision':1}
        with patch.object(organizer,'request_json',side_effect=[
            ({'blocks':[{'kind':'paragraph','text':'可以保留的完整文章。'}]},{}),
            ({'blocks':[{'kind':'paragraph','text':'长'*601}]},{})]):
            organizer.run(job,self.task,documents.get(self.task))
        self.assertEqual(job['status'],'completed')
        self.assertIn('summary_error',job)
        self.assertNotIn('essence_content',job)
        self.assertEqual(documents.text(job['content']),'可以保留的完整文章。')

    def test_truncated_model_output_is_not_a_manuscript(self):
        response=type('Response',(),{'status_code':200,'json':lambda self:{'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}})()
        with patch.object(organizer.httpx.Client,'post',return_value=response):
            with self.assertRaisesRegex(RuntimeError,'截断'):
                organizer.request_json('test','test')

    def test_rejects_invalid_schema_and_strips_marks(self):
        with self.assertRaises(ValueError):documents.validate({'type':'doc','content':[{'type':'text','text':'bad'}]})
        with self.assertRaises(ValueError):documents.validate({'type':'doc','content':[{'type':'iframe'}]})
        value=documents.validate({'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'safe','marks':[{'type':'link','attrs':{'href':'javascript:bad'}}]}]}]})
        self.assertEqual(value['content'][0]['content'][0]['marks'],[])

    def test_api_export_and_conflict_and_origin(self):
        with TestClient(app.app) as client:
            path='/api/studio/documents/'+self.task['id']
            doc=client.get(path).json()
            body={'revision':doc['revision'],'content':doc['content']}
            self.assertEqual(client.put(path,json=body,headers={'Origin':'https://evil.test'}).status_code,403)
            self.assertEqual(client.put(path,json=body).status_code,200)
            self.assertEqual(client.put(path,json=body).status_code,409)
            self.assertIn('第一句',client.get(path+'/export/txt').text)
            self.assertEqual(client.get(path+'/versions/1').status_code,200)


if __name__=='__main__':unittest.main()
