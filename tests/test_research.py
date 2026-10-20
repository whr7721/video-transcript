import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import documents
import research
import settings
import store
from research_api import ResearchInput


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'test.sqlite3'),patch.object(settings,'FILE',root/'settings.json')]
        for p in self.patches:p.start()
        store.init()
        self.task={'id':'bbbbbbbbbbbbbbbb','status':'completed','created_at':time.time(),'title':'研究样本','result':{'text':'公开过程可以帮助建立连接。','segments':[{'text':'公开过程可以帮助建立连接。','start':0,'end':4}]}}
        store.save(self.task)

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def job(self,online=False,mode='explain'):
        job={'id':'job123','task_id':self.task['id'],'title':'研究样本','mode':mode,'online':online,'question':'有什么前提？',
             'context':research.context(self.task,'original',1,None,'公开过程'),'status':'queued','stage':'queued',
             'created_at':time.time(),'usage':[],'warnings':[],'sources':[],'tool_cost_estimate':0}
        research.save(job);return job

    def test_selected_passage_and_revision_are_validated(self):
        with self.assertRaises(ValueError):research.context(self.task,'original',1,None,'不存在的引文')
        with self.assertRaises(documents.Conflict):research.context(self.task,'draft',2,None,'公开过程')
        with self.assertRaises(ValueError):research.context(self.task,'manuscript',1,'fake','公开过程')
        self.assertEqual(research.context(self.task,'original',1,None,'公开\n过程')['selection'],'公开\n过程')

    def test_only_safe_public_links_are_renderable(self):
        for url in ['http://localhost/','http://127.0.0.1/','http://10.0.0.1/','file:///etc/passwd','https://user:pass@example.com/','https://example.com:8765/','javascript:alert(1)']:
            self.assertIsNone(research.public_url(url))
        self.assertEqual(research.public_url('https://example.com/case?utm_source=x&id=1#part'),'https://example.com/case?id=1')

    def test_cases_require_actual_source_quote(self):
        source={'id':'web-1','kind':'web','body':'公司先发布过程，再收集反馈。'}
        value={'sections':[{'text':'有来源的案例','citations':[{'source_id':'web-1','quote':'先发布过程，再收集反馈'}]},
                           {'text':'捏造案例','citations':[{'source_id':'web-1','quote':'公司赚了100万元'}]}]}
        sections,rejected=research.checked_sections(value,[source],'cases')
        self.assertEqual(len(sections),1);self.assertEqual(rejected,1)

    def test_quote_presence_does_not_replace_support_review(self):
        sections=[{'heading':'案例','text':'公司收入增加了十倍','basis':'has_source_excerpt',
                   'citations':[{'source_id':'web-1','quote':'公司公开了过程'}]}]
        source={'id':'web-1','kind':'web','body':'公司公开了过程，但未公布任何收入。'}
        with patch.object(research.organizer,'request_json',return_value=({'reviews':[{'index':0,'supported':False,'reason':'来源没有收入数字'}]},{})) as request:
            good,rejected,_=research.check_support(sections,[source],'cases',request)
        self.assertEqual(good,[]);self.assertEqual(rejected,1)

    def test_cases_disclaimers_override_positive_model_review(self):
        sections=[{'heading':'二手转述案例','text':'匿名故事数字无法独立核实。','citations':[{'source_id':'web-1','quote':'故事'}]},
                  {'heading':'与本题无关','text':'这是股票资料。','citations':[{'source_id':'web-1','quote':'股票'}]}]
        def request(*args):return {'reviews':[{'index':i,'supported':True,'reason':'文字出现'} for i in range(2)]},{}
        good,rejected,_=research.check_support(sections,[{'id':'web-1','body':'故事和股票资料'}],'cases',request,'公开创作能否赚钱')
        self.assertEqual(good,[]);self.assertEqual(rejected,2)

    def test_online_flow_uses_web_source_and_checks_support(self):
        job=self.job(True,'cases')
        source={'id':'web-1','kind':'web','url':'https://example.com/case','title':'真实记录','body':'团队公开制作过程并收集反馈。'*20,'retrieved_at':time.time()}
        answers=[({'queries':['公开过程真实案例']},{}),
                 ({'sections':[{'heading':'案例','text':'团队公开过程并获得反馈。','citations':[{'source_id':'web-1','quote':'团队公开制作过程并收集反馈'}]}]},{}),
                 ({'reviews':[{'index':0,'supported':True,'reason':'实际记录支持该段事实'}]}, {})]
        with patch.object(research,'collected_sources',return_value=[source]),patch.object(research.organizer,'request_json',side_effect=answers) as request:
            research.run(job)
        self.assertEqual(request.call_count,3);self.assertEqual(job['status'],'completed')
        self.assertEqual(job['sections'][0]['support_status'],'model_checked')

    def test_cancelled_request_can_be_explicitly_restarted(self):
        body=ResearchInput(selection='公开过程',question='解释',online=False)
        with patch.object(settings,'cloud_key',return_value='fake'),patch.object(research.EXECUTOR,'submit'):
            job=research.start(self.task,body);research.cancel(job['id'])
            restarted=research.start(self.task,body)
        self.assertEqual(restarted['status'],'queued')
        self.assertEqual(research.get(job['id'])['status'],'queued')

    def test_unconfigured_search_fails_without_inference(self):
        with patch.object(settings,'search_key',return_value=''),patch.object(research.EXECUTOR,'submit') as submit:
            with self.assertRaisesRegex(ValueError,'搜索 Key'):
                research.start(self.task,ResearchInput(selection='公开过程',online=True))
        submit.assert_not_called()

    def test_offline_explanation_does_not_claim_web_verification(self):
        job=self.job()
        with patch.object(research.organizer,'request_json',return_value=({'sections':[{'heading':'解释','text':'这是解释，不是案例核实。','citations':[]}],'open_questions':[]},{})):
            research.run(job)
        self.assertEqual(job['status'],'completed')
        self.assertEqual(job['sections'][0]['basis'],'model_analysis')
        self.assertIn('未联网',job['warnings'][0])
        self.assertEqual(documents.get(self.task)['revision'],1)
        self.assertEqual(store.get(self.task['id'])['result']['text'],'公开过程可以帮助建立连接。')

    def test_search_deduplicates_and_caps_queries_without_redundant_fetch(self):
        job=self.job(True)
        answer={'results':[{'url':'https://example.com/a?utm_source=x','title':'案例','content':'真实案例正文。'*30},
                           {'url':'https://example.com/a','title':'重复','content':'真实案例正文。'*30}]}
        with patch.object(research,'tool',return_value=answer) as tool:
            sources=research.collected_sources(job,['one','two','three','four'])
        self.assertEqual(tool.call_count,3);self.assertEqual(len(sources),1)

    def test_partial_search_results_survive_later_query_failure(self):
        job=self.job(True)
        with patch.object(research,'tool',side_effect=[{'results':[{'url':'https://example.com/a','content':'材料。'*40}]},RuntimeError('限流')]):
            sources=research.collected_sources(job,['one','two'])
        self.assertEqual(len(sources),1);self.assertIn('限流',job['warnings'])

    def test_cancelled_job_cannot_publish_or_call_model(self):
        job=self.job();research.cancel(job['id'])
        with patch.object(research.organizer,'request_json') as request:research.run(job)
        request.assert_not_called();self.assertEqual(research.get(job['id'])['status'],'cancelled')

    def test_notes_persist_personal_understanding_and_references(self):
        job=self.job();job.update(status='completed',sections=[{'heading':'理解','text':'解释正文','citations':[]}]);research.save(job)
        note=research.save_note(job['id'],'公开构建','对我的项目有帮助。')
        with self.assertRaises(ValueError):research.save_note(job['id'],'公开构建','不应覆盖')
        note=research.update_note(note['id'],1,'更新自己的理解')
        with self.assertRaises(documents.Conflict):research.update_note(note['id'],1,'过时写入')
        text=research.export_note(note['id']);self.assertIn('更新自己的理解',text);self.assertIn(self.task['id'],text)
        self.assertEqual(research.topics()[0]['notes_count'],1)

    def test_tool_cache_avoids_repeated_billing(self):
        response=type('Response',(),{'status_code':200,'json':lambda self:{'results':[{'url':'https://example.com'}]}})()
        job=self.job(True)
        with patch.object(settings,'search_key',return_value='secret-not-printed'),patch.object(research.httpx.Client,'post',return_value=response) as post:
            research.tool('search',{'query':'公开构建'},job);research.tool('search',{'query':'公开构建'},job)
        self.assertEqual(post.call_count,1);self.assertAlmostEqual(job['tool_cost_estimate'],.005)

    def test_api_notes_export_and_cross_site_rejection(self):
        job=self.job();job.update(status='completed',sections=[]);research.save(job)
        with TestClient(app.app) as client:
            body={'job_id':job['id'],'topic_title':'学习','personal':'我的理解'}
            path='/api/studio/research/notes'
            self.assertEqual(client.post(path,json=body,headers={'Origin':'https://evil.test'}).status_code,403)
            note=client.post(path,json=body).json()
            self.assertEqual(client.get(path+'/'+note['id']+'/export').status_code,200)

    def test_search_key_is_separate_encrypted_and_never_returned(self):
        with patch.dict(settings.os.environ,{'DEEPSEEK_API_KEY':'','SILICONFLOW_API_KEY':''}):
            settings.save('local','model-test-key','search-test-key')
            raw=settings.FILE.read_text(encoding='utf-8');self.assertNotIn('search-test-key',raw);self.assertNotIn('model-test-key',raw)
            self.assertEqual(settings.search_key(),'search-test-key');self.assertEqual(settings.cloud_key(),'model-test-key')
            public=json.dumps(settings.public());self.assertNotIn('search-test-key',public);self.assertNotIn('encrypted_search_key',public)


if __name__=='__main__':unittest.main()
