import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app,documents,organizer,research,settings,store


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'tasks.sqlite3'),patch.object(settings,'FILE',root/'settings.json')]
        for p in self.patches:p.start()
        store.init();self.task={'id':'c'*16,'title':'本地文稿','source':{'kind':'local_file','original_name':'讲话.mp3'},'status':'completed','created_at':time.time(),
                             'result':{'text':'先理解，再验证。','segments':[{'text':'先理解，再验证。','start':0,'end':4}]}}
        store.save(self.task)
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def test_manual_note_without_keys_has_provenance_and_exports_without_ai_label(self):
        with TestClient(app.app) as c,patch('organizer.request_json',side_effect=AssertionError('no AI')),patch('research.tool',side_effect=AssertionError('no search')):
            doc=c.get('/api/studio/documents/'+self.task['id']).json()
            before=store.get(self.task['id'])
            payload={'basis':'original','revision':doc['revision'],'selection':'先理解','topic_title':'离线学习','personal':'我会记录可验证的假设。'}
            r=c.post('/api/studio/research/documents/'+self.task['id']+'/manual-note',json=payload)
            self.assertEqual(r.status_code,200,r.text)
            note=r.json();job=research.get(note['job_id'])
            self.assertEqual(job['mode'],'manual');self.assertFalse(job['online']);self.assertIsNone(job['model'])
            exported=c.get('/api/studio/research/notes/'+note['id']+'/export').text
            self.assertIn('先理解',exported);self.assertIn('未调用AI',exported);self.assertNotIn('深入结果（AI生成',exported)
            self.assertEqual(store.get(self.task['id']),before)
            self.assertEqual(documents.get(self.task)['revision'],doc['revision'])
            self.assertEqual(research.note_list()[0]['id'],note['id'])

    def test_manual_note_rejects_stale_revision_and_fake_selection(self):
        from research_api import ManualNote
        for changes in ({'basis':'draft','revision':99},{'selection':'原文没有这句'}):
            payload={'basis':'original','revision':1,'selection':'先理解','topic_title':'学习','personal':'理解',**changes}
            with self.assertRaises((ValueError,documents.Conflict)):research.manual_note(self.task,ManualNote(**payload))
        self.assertEqual(research.note_list(),[])

    def test_capacity_rejected_before_job_queue_or_model(self):
        self.task['result']={'text':'长'*24001,'segments':[{'text':'长'*1000,'start':i,'end':i+1} for i in range(25)]};store.save(self.task)
        doc=documents.get(self.task)
        with patch('organizer.EXECUTOR.submit') as submit,patch('settings.cloud_key',return_value='configured'):
            with self.assertRaisesRegex(ValueError,'24000'):organizer.start(self.task,'manuscript',doc['revision'])
            submit.assert_not_called()
        with store.connect() as db:self.assertEqual(db.execute('SELECT count(*) FROM generations').fetchone()[0],0)
        self.assertFalse(organizer.capabilities(self.task)['manuscript']['available'])
        self.assertEqual(research.context(self.task,'original',1,None,'长长')['selection'],'长长')

    def test_chunk_capacity_rejected_without_partial_calls(self):
        self.task['result']={'text':'短','segments':[{'text':'字'*6000,'start':i,'end':i+1} for i in range(9)]}
        with patch('organizer.EXECUTOR.submit') as submit,patch('settings.cloud_key',return_value='configured'):
            with self.assertRaisesRegex(ValueError,'8块'):organizer.start(self.task,'summary',1)
            submit.assert_not_called()


if __name__=='__main__':unittest.main()
