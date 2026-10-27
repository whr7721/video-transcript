import copy
import tempfile
import time
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import documents
import mindmap
import organizer
import public_quota
import store


TREE={'root':{'text':'学习方法','children':[{'text':'概念','children':[{'text':'区别'}]},
                                          {'text':'应用','children':[{'text':'区别'}]}]}}


class SyncExecutor:
    def submit(self,fn,*args):
        future=Future();future.set_result(fn(*args));return future


class MindmapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        public_quota._reset_for_tests()
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'tasks.sqlite3'),
                      patch.object(organizer,'EXECUTOR',SyncExecutor()),patch.object(organizer.settings,'cloud_key',return_value='test')]
        for p in self.patches:p.start()
        store.init()
        self.task={'id':'eeeeeeeeeeeeeeee','status':'completed','title':'学习','created_at':time.time(),
                   'result':{'text':'原始全文。学习概念并练习应用。','segments':[]}}
        store.save(self.task)

    def tearDown(self):
        public_quota._reset_for_tests()
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_invalid_tree_never_silently_drops_nodes(self):
        bad=[{}, {'root':None},{'root':{'text':'a','children':'bad'}},
             {'root':{'text':'a','children':[{'text':str(i)} for i in range(9)]}},
             {'root':{'text':'a','children':[{'text':'a1'},{'text':'a1'}]}},
             {'root':{'text':'<script>alert(1)</script>'}}, {'root':{'text':'line\nbreak'}},
             {'root':{'text':'a'*41}}]
        deep={'text':'5'}
        for i in range(4):deep={'text':str(i),'children':[deep]}
        bad.append({'root':deep})
        broad={'root':{'text':'root','children':[{'text':f'b{i}','children':[
            {'text':f'c{j}','children':[{'text':f'd{k}'} for k in range(2)]} for j in range(8)]} for i in range(4)]}}
        bad.append(broad)
        for value in bad:
            with self.subTest(value=value),self.assertRaises(ValueError):mindmap.validate(value)
        self.assertEqual(mindmap.validate(TREE)['children'][1]['children'][0]['text'],'区别')
        self.assertIn('&lt;',mindmap.to_markdown({'text':'x < 5','children':[]}))

    def test_full_source_limits_are_not_summary_chunk_limits(self):
        task={**self.task,'result':{'text':'长'*24000}}
        self.assertTrue(organizer.capabilities(task)['mindmap']['available'])
        self.assertFalse(organizer.capabilities(task)['summary']['available'])
        for raw in ['', '长'*24001]:
            task={**self.task,'result':{'text':raw}}
            self.assertFalse(organizer.capabilities(task)['mindmap']['available'])
            with patch.object(organizer,'request_json') as request,self.assertRaises(ValueError):
                organizer.start(task,'mindmap',1)
            request.assert_not_called()

    def test_cache_survives_draft_edits_and_export_is_specific(self):
        before=copy.deepcopy(self.task)
        doc=documents.get(self.task)
        with patch.object(organizer,'request_json',return_value=(TREE,{'total_tokens':100})) as request:
            job=organizer.start(self.task,'mindmap',doc['revision'])
            self.assertEqual(request.call_args.kwargs['schema'],mindmap.SCHEMA)
            changed=documents.save(self.task,1,{'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':'我的编辑'}]}]})
            again=organizer.start(self.task,'mindmap',changed['revision'])
            self.assertEqual(again['id'],job['id']);self.assertEqual(request.call_count,1)
        self.assertEqual(store.get(self.task['id'])['result'],before['result'])
        self.assertEqual(documents.text(documents.get(self.task)['content']),'我的编辑')
        result=documents.generation_get(job['id'])
        self.assertEqual(result['source_basis'],'immutable_asr')
        response=TestClient(app.app).get(f'/api/studio/generations/{job["id"]}/mindmap.md')
        self.assertEqual(response.status_code,200);self.assertIn('# 学习方法',response.text)
        self.assertIn('attachment',response.headers['content-disposition'])
        self.assertEqual(TestClient(app.app).get('/api/studio/generations/unknown/mindmap.md').status_code,404)

    def test_two_tasks_with_identical_text_do_not_share_identity(self):
        with patch.object(organizer,'request_json',return_value=(TREE,{})):
            first=organizer.start(self.task,'mindmap',1)
            other={**self.task,'id':'aaaaaaaaaaaaaaaa'};store.save(other)
            second=organizer.start(other,'mindmap',1)
        self.assertNotEqual(first['id'],second['id'])

    def test_failed_candidate_keeps_charged_usage_and_old_results(self):
        old={'id':'old-map','task_id':self.task['id'],'action':'mindmap','status':'completed','mindmap':TREE['root']}
        documents.generation_save(old)
        with patch.object(organizer,'request_json',return_value=({'root':None},{'total_tokens':50})):
            job=organizer.start(self.task,'mindmap',1)
        result=documents.generation_get(job['id'])
        self.assertEqual(result['status'],'failed');self.assertEqual(result['total_tokens'],50)
        self.assertEqual(documents.generation_get('old-map')['status'],'completed')

    def test_public_mindmap_uses_editorial_quota_only(self):
        with patch.object(public_quota,'PUBLIC',True),patch.object(organizer,'request_json',return_value=(TREE,{})):
            client=TestClient(app.app)
            headers={'X-Device-Id':'testdevice123'}
            responses=[client.post(f'/api/studio/documents/{self.task["id"]}/generate',
                        json={'action':'mindmap','revision':1},headers=headers) for _ in range(4)]
            self.assertEqual([r.status_code for r in responses],[200,200,200,429])
            self.assertEqual(client.post(f'/api/studio/documents/{self.task["id"]}/generate',
                            json={'action':'paragraphs','revision':1},headers=headers).status_code,200)

    def test_markdown_preserves_literal_special_characters(self):
        result=mindmap.to_markdown({'text':'[标签](javascript:alert(1))','children':[]})
        self.assertIn(r'\[标签\]',result)
        self.assertNotIn('[标签](',result)

    def test_publisher_source_is_identified_without_inventing_asr(self):
        task={**self.task,'source':{'ingest':'publisher_text'}};job={}
        mindmap.run(job,task,lambda *args:(TREE,{'total_tokens':5}))
        self.assertEqual(job['source_basis'],'immutable_publisher')
        self.assertEqual(task['result'],self.task['result'])

if __name__=='__main__':unittest.main()
