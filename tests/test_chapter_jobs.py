import copy
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_chapters as chapter_tests
import chapters
import chapter_jobs as jobs
import documents
import research
import store


class ChapterJobTests(unittest.TestCase):
    setUp=chapter_tests.ChapterStorageTests.setUp
    tearDown=chapter_tests.ChapterStorageTests.tearDown
    def model(self,system,user,max_tokens=1400):
        value=json.loads(user)
        if 'merge_after' in system:return {'merge_after':[]},{'total_tokens':10}
        if 'core' in value:
            first=value['core'][0]
            return {'sections':[{'start_id':first['id'],'title':'主题','guide':'讨论原文的具体问题与条件。',
                                 'evidence_id':first['id'],'quote':first['text'][:8]}]},{'total_tokens':10}
        return {'blocks':[{'kind':'paragraph','text':value}], 'uncertainties':[]},{'total_tokens':10}

    def directory(self):
        self.task['result']['segments']=[{'text':('长内容与具体条件。'*700),'start':0,'end':120}]
        view=chapters.snapshot(self.task)
        job={'id':'test-directory','task_id':self.task['id'],'action':'directory','status':'queued','usage':[],'calls':0}
        jobs.put(job)
        with patch.object(jobs.organizer,'request_json',side_effect=self.model) as model:
            jobs.run(job,view)
            self.assertEqual(jobs.get(job['id'])['status'],'completed',jobs.get(job['id']))
            count=model.call_count
        return view,job,count

    def test_checkpoints_reuse_windows_and_merge(self):
        view,job,count=self.directory()
        self.assertGreater(count,1)
        job['status']='queued';jobs.put(job)
        with patch.object(jobs.organizer,'request_json',side_effect=AssertionError('cached stages must not call')):
            jobs.run(job,view)
        self.assertEqual(jobs.get(job['id'])['status'],'completed')
        self.assertTrue(chapters.validate(view,jobs.get(job['id'])['plan']))

    def test_failure_resume_does_not_repeat_completed_window(self):
        text='案例和条件。'*1400
        task={'id':'repeat','result':{'segments':[{'text':text}]}}
        view=chapters.snapshot(task)
        job={'id':'retry','task_id':'repeat','action':'directory','status':'queued','usage':[],'calls':0}
        jobs.put(job);calls=[0]
        def fail(system,user,max_tokens):
            calls[0]+=1
            if calls[0]==2:raise RuntimeError('timeout')
            return self.model(system,user,max_tokens)
        with patch.object(jobs.organizer,'request_json',side_effect=fail):jobs.run(job,view)
        self.assertEqual(jobs.get('retry')['status'],'paused')
        self.assertEqual(jobs.get('retry')['completed_windows'],1)
        job['status']='queued';jobs.put(job)
        with patch.object(jobs.organizer,'request_json',side_effect=self.model) as model:
            jobs.run(job,view)
            self.assertEqual(model.call_count,2) # failed window + merge only
        self.assertEqual(jobs.get('retry')['status'],'completed')

    def test_cancel_during_request_retains_checkpoint_no_later_calls(self):
        view=chapters.snapshot({'id':'cancel','result':{'text':'长内容。'*2000}})
        job={'id':'cancel','task_id':'cancel','action':'directory','status':'queued','usage':[],'calls':0}
        jobs.put(job)
        def cancel(system,user,max_tokens):
            result=self.model(system,user,max_tokens);jobs.cancel('cancel');return result
        with patch.object(jobs.organizer,'request_json',side_effect=cancel) as model:jobs.run(job,view)
        self.assertEqual(model.call_count,1)
        self.assertEqual(jobs.get('cancel')['status'],'cancelled')
        self.assertIsNotNone(jobs.cache(jobs.window_key(view,jobs.windows(view)[0])))

    def test_budget_reject_before_request_and_restart_pauses(self):
        with patch.object(jobs.settings,'cloud_key',return_value='test'),patch.object(jobs,'quota',return_value={'used':30,'limit':30,'remaining':0}):
            with self.assertRaises(ValueError):jobs.start(self.task,'directory',0)
        job={'id':'interrupted','task_id':'sample','status':'running'};jobs.put(job);jobs.recover()
        self.assertEqual(jobs.get('interrupted')['status'],'paused')

    def test_chapter_context_exact_duplicate_and_old_revision(self):
        store.init();store.save(self.task)
        view=chapters.snapshot(self.task);parts=chapters.fragments(view)
        plan=chapters.reading_sections(view)
        plan['sections']=[{'title':'一','fragment_ids':[parts[0]['id']]},{'title':'二','fragment_ids':[parts[1]['id']]}]
        saved=chapters.save(self.task,plan,0)
        ctx=research.context(self.task,'chapter',1,None,'重复句。',1,1,0)
        self.assertEqual(ctx['source_ranges'][0]['source_id'],'seg-1')
        plan['sections'][1]['title']='新名称';chapters.save(self.task,plan,1)
        self.assertEqual(research.context(self.task,'chapter',1,None,'重复句。',1,1,0)['version'],'chapter-1-1')
        with self.assertRaises(ValueError):research.context(self.task,'chapter',1,None,'重复句。',1,1,1)
        body=SimpleNamespace(basis='chapter',revision=1,generation_id=None,selection='重复句。',chapter_revision=1,chapter_index=1,selection_start=0,personal='我自己的理解',topic_title='主题')
        note=research.manual_note(self.task,body)
        # Export must carry precise scope, not just an ambiguous repeated quote.
        self.assertIn('seg-1',research.export_note(note['id']))

    def test_reject_wrong_evidence_and_large_source(self):
        view=chapters.snapshot(self.task);window=jobs.windows(view)[0]
        with self.assertRaises(ValueError):jobs.checked(window,{'sections':[{'start_id':window['core'][0]['id'],'title':'题','guide':'导读','evidence_id':'fake','quote':'原话'}]})
        with self.assertRaises(ValueError):jobs.windows(chapters.snapshot({'id':'big','result':{'text':'字'*60001}}))

    def test_parent_alias_only_if_unambiguous(self):
        view=chapters.snapshot(self.task);window=jobs.windows(view)[0]
        first=window['core'][0]
        result=jobs.checked(window,{'sections':[{'start_id':first['source_id'],'title':'主题','guide':'原话导读','evidence_id':first['source_id'],'quote':first['text']} ]})
        self.assertEqual(result[0]['fragment_ids'][0],first['id'])
        view=chapters.snapshot({'id':'long','result':{'text':'语句。'*1000}});window=jobs.windows(view)[0]
        with self.assertRaises(ValueError):jobs.checked(window,{'sections':[{'start_id':'seg-0','title':'主题','guide':'导读','evidence_id':'seg-0','quote':'语句。'}]})

    def test_aggressive_merges_cannot_swallow_entire_document(self):
        self.task['result']['segments']=[{'text':'不同主题和条件。'*1800}]
        view=chapters.snapshot(self.task)
        job={'id':'overmerge','task_id':self.task['id'],'action':'directory','status':'queued','usage':[],'calls':0}
        jobs.put(job)
        def model(system,user,max_tokens):
            value=json.loads(user)
            if 'merge_after' in system:return {'merge_after':list(range(len(value)-1))},{'total_tokens':10}
            core=value['core'];middle=len(core)//2
            return {'sections':[{'start_id':core[i]['id'],'title':str(i),'guide':'不同的主题应保留。','evidence_id':core[i]['id'],'quote':core[i]['text'][:10]} for i in sorted({0,middle})]},{'total_tokens':10}
        with patch.object(jobs.organizer,'request_json',side_effect=model):jobs.run(job,view)
        value=jobs.get(job['id']);self.assertEqual(value['status'],'completed')
        self.assertGreaterEqual(len(value['plan']['sections']),3)

    def test_apply_conflict_and_chapter_export_does_not_change_draft(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from studio_api import router
        store.init();store.save(self.task)
        before=documents.get(self.task)
        view=chapters.snapshot(self.task);plan=chapters.reading_sections(view)
        job={'id':'ready','task_id':self.task['id'],'action':'directory','status':'completed','plan':plan}
        jobs.put(job);app=FastAPI();app.include_router(router);c=TestClient(app)
        base='/api/studio/documents/'+self.task['id']
        self.assertEqual(c.post(base+'/chapter-jobs/ready/apply',json={'revision':0}).status_code,200)
        self.assertEqual(c.post(base+'/chapter-jobs/ready/apply',json={'revision':0}).status_code,409)
        response=c.get(base+'/chapters/export/md');self.assertEqual(response.status_code,200)
        self.assertIn(view['source_hash'],response.text)
        self.assertEqual(documents.get(self.task)['content'],before['content'])
