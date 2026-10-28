import unittest
from unittest.mock import patch
from fastapi import HTTPException
import tests.test_personal_kb as fixtures
import knowledge_projects as projects

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.KnowledgeTests();self.fixture.setUp()
        self.project=projects.create(projects.New(title='摄影学习',goal='掌握曝光基本概念'))
    def tearDown(self):self.fixture.tearDown()
    def edit(self,p):return projects.edit(p['id'],projects.Edit(revision=p['revision'],goal=p['goal'],constraints=p['constraints'],steps=p['steps'],review=p['review']))
    def test_progress_and_conflict(self):
        p=self.project;p['steps']=[{'id':'one','title':'练习曝光','state':'done','detail':'比较照片','note':'已完成第一组'}]
        saved=self.edit(p);self.assertEqual(saved['revision'],2)
        self.assertEqual(projects.listing()[0]['steps'][0]['note'],'已完成第一组')
        with self.assertRaises(HTTPException) as ctx:self.edit(p)
        self.assertEqual(ctx.exception.status_code,409)
    def test_adoption_preserves_history_and_citations(self):
        p=self.project;p['steps']=[{'id':'old','title':'旧计划','state':'done','detail':'','note':'原进度'}];p=self.edit(p)
        job={'status':'completed','stale':False,'result':{'sections':[{'heading':'新计划','text':'练习构图','citations':[{'title':'来源','url':'/studio/','quote':'原话'}]}],'gaps':[]}}
        with patch.object(projects.kb,'read',return_value=job):p=projects.adopt(p['id'],projects.Adopt(revision=p['revision'],job_id='fixture'))
        self.assertEqual(p['versions'][0]['steps'][0]['note'],'原进度')
        p['steps'][0]['state']='doing';p=self.edit(p)
        self.assertEqual(p['steps'][0]['citations'][0]['quote'],'原话')
    def test_research_receives_goal_and_progress(self):
        p=self.project;p['constraints']='每周45分钟';p=self.edit(p)
        with patch.object(projects.kb,'ask',return_value={'id':'fake'}) as ask:
            self.assertEqual(projects.research(p['id'])['id'],'fake')
            self.assertIn('每周45分钟',ask.call_args.args[0].question)
    def test_stale_or_empty_research_cannot_be_adopted(self):
        for j in [{'status':'completed','stale':True,'result':{'sections':[{}]}},{'status':'completed','result':{'sections':[]}}]:
            with patch.object(projects.kb,'read',return_value=j):
                with self.assertRaises(HTTPException):projects.adopt(self.project['id'],projects.Adopt(revision=1,job_id='fixture'))
