import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import personal_kb as kb
import store

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.p1=patch.object(store,'DATA',root);self.p2=patch.object(store,'DB',root/'tasks.sqlite3');self.p1.start();self.p2.start()
        with store.connect() as db:
            kb.init(db);db.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,payload TEXT)');db.execute('CREATE TABLE article_items(id TEXT PRIMARY KEY,payload TEXT)')
            task={'id':'audio-fixture','status':'completed','title':'养花经验','result':{'text':'多肉浇水需要检查土壤干湿，不能每天固定浇水。'}}
            item={'id':'article-fixture','status':'ready','title':'摄影基础','blocks':[{'id':'b','type':'paragraph','text':'摄影曝光由光圈、快门和感光度共同决定。'}]}
            db.execute('INSERT INTO tasks VALUES (?,?)',(task['id'],json.dumps(task)))
            db.execute('INSERT INTO article_items VALUES (?,?)',(item['id'],json.dumps(item)))
    def tearDown(self):self.p2.stop();self.p1.stop();self.temp.cleanup()
    def test_unified_retrieval_and_scope(self):
        state=kb.sync();self.assertEqual(sum(g['sources'] for g in state['groups']),2)
        self.assertIn('土壤',kb.search('多肉浇水')[0]['text'])
        self.assertEqual(kb.search('光圈','audio'),[])
        self.assertEqual(kb.search('光圈','article')[0]['kind'],'article')
        self.assertEqual(kb.sync()['fingerprint'],state['fingerprint'])
    def test_explicit_memory_update_and_remove(self):
        a=kb.remember(kb.Memory(title='个人偏好',text='喜欢简洁的旅行计划'))
        kb.remember(kb.Memory(title='个人偏好',text='喜欢有时间预算的旅行计划'));kb.sync()
        self.assertEqual(len(kb.search('旅行','memory')),1)
        kb.forget(a['id']);kb.sync();self.assertEqual(kb.search('旅行','memory'),[])
    def test_citations_must_have_been_read_and_match(self):
        kb.sync();p=kb.search('摄影光圈')[0]
        value={'sections':[{'heading':'摄影','text':'控制曝光','citations':[{'id':p['id'],'quote':'光圈、快门和感光度共同决定'}]},{'text':'无依据观点','citations':[{'id':'invented','quote':'不存在的引文'}]}],'gaps':[]}
        result=kb.validate_answer(value,{p['id']:p});self.assertEqual(len(result['sections']),1);self.assertGreater(result['rejected'],0)
        self.assertEqual(kb.validate_answer(value,{})['sections'],[])
    def test_actual_tool_loop_contract(self):
        kb.sync();p=kb.search('多肉浇水')[0]
        tool=lambda name,args:{'role':'assistant','content':None,'tool_calls':[{'id':name,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}]}
        outputs=[tool('search_library',{'query':'多肉浇水'}),tool('read_passages',{'ids':[p['id']]}),{'role':'assistant','content':json.dumps({'sections':[{'heading':'浇水','text':'先检查土壤','citations':[{'id':p['id'],'quote':'浇水需要检查土壤干湿'}]}],'gaps':[]})}]
        job={'id':'fixture-job','question':'怎么给多肉浇水','mode':'answer','kind':'all','status':'queued'}
        with patch.object(kb,'model',side_effect=outputs) as m:kb.run(job,{p['id']:p})
        self.assertEqual(job['status'],'completed');self.assertEqual(m.call_count,3);self.assertEqual(len(job['trace']),2)
        self.assertEqual(kb.get(job['id'])['result']['sections'][0]['citations'][0]['id'],p['id'])
    def test_foreign_read_and_turn_limit(self):
        tool={'role':'assistant','tool_calls':[{'id':'bad','function':{'name':'read_passages','arguments':'{"ids":["unknown"]}'}}]}
        job={'id':'bad','question':'问题','mode':'answer','kind':'all'}
        with patch.object(kb,'model',return_value=tool):kb.run(job,{})
        self.assertEqual(job['status'],'failed')
        loop={'role':'assistant','tool_calls':[{'id':'search','function':{'name':'search_library','arguments':'{"query":"missing"}'}}]}
        job={'id':'loop','question':'问题','mode':'answer','kind':'all'}
        with patch.object(kb,'model',return_value=loop) as m:kb.run(job,{})
        self.assertEqual(m.call_count,4);self.assertEqual(job['status'],'failed')
    def test_budget_rejects_before_any_provider_request(self):
        with patch.object(kb.organizer,'reserve_daily_call'),patch.object(kb.httpx,'Client') as client:
            with self.assertRaises(RuntimeError):kb.model([{'role':'user','content':'文'*1_000_000}],kb.TOOLS)
            client.assert_not_called()
        self.assertEqual(kb.budget()['calls'],0)
    def test_ask_is_cached_without_repeating_tools(self):
        class Sync:
            def submit(self,fn,*args):fn(*args)
        kb.sync();p=kb.search('摄影')[0]
        responses=[{'role':'assistant','tool_calls':[{'id':'s','type':'function','function':{'name':'search_library','arguments':'{"query":"摄影"}'}}]},
                   {'role':'assistant','tool_calls':[{'id':'r','type':'function','function':{'name':'read_passages','arguments':json.dumps({'ids':[p['id']]})}}]},
                   {'role':'assistant','content':json.dumps({'sections':[{'heading':'曝光','text':'有三个要素','citations':[{'id':p['id'],'quote':'光圈、快门和感光度共同决定'}]}],'gaps':[]})}]
        with patch.object(kb,'EXECUTOR',Sync()),patch.object(kb.settings,'cloud_key',return_value='fixture'),patch.object(kb,'model',side_effect=responses) as m:
            a=kb.ask(kb.Ask(question='摄影曝光'))
            b=kb.ask(kb.Ask(question='摄影曝光'))
            self.assertEqual(a['id'],b['id']);self.assertEqual(b['status'],'completed');self.assertEqual(m.call_count,3)
    def test_changed_source_removes_cached_passage(self):
        kb.sync();old=kb.search('多肉')[0]['id']
        with store.connect() as db:
            task=json.loads(db.execute('select payload from tasks').fetchone()[0]);task['result']['text']='摄影新内容';db.execute('update tasks set payload=?',(json.dumps(task),))
        kb.sync();self.assertEqual(kb.search('多肉'),[])
        self.assertNotIn(old,[p['id'] for p in kb.search('摄影')])
