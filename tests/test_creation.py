import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import creation
import store

class Sync:
    def submit(self,fn,*args):fn(*args)

class CreationTests(unittest.TestCase):
    def test_manual_templates_need_no_key_or_model(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(store,'DATA',Path(folder)),patch.object(store,'DB',Path(folder)/'tasks.sqlite3'),patch.object(creation.settings,'cloud_key',return_value=''),patch.object(creation.image_editorial,'request') as call:
            for task in creation.TASKS:
                job=creation.start(creation.Input(source='资料',mode='manual',task=task,platform='toutiao'))
                self.assertEqual(job['status'],'completed')
                self.assertEqual(job['brief']['task'],task)
                self.assertEqual(len(job['result']['cards']),5)
            call.assert_not_called()
    def test_platform_and_task_have_distinct_cache(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(store,'DATA',Path(folder)),patch.object(store,'DB',Path(folder)/'tasks.sqlite3'):
            a=creation.start(creation.Input(source='资料',mode='manual'))
            b=creation.start(creation.Input(source='资料',mode='manual',platform='toutiao'))
            c=creation.start(creation.Input(source='资料',mode='manual',task='review'))
            self.assertEqual(len({a['id'],b['id'],c['id']}),3)
    def test_generation_cache_and_immutable_input(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(store,'DATA',Path(folder)),patch.object(store,'DB',Path(folder)/'tasks.sqlite3'),patch.object(creation.settings,'cloud_key',return_value='fixture'),patch.object(creation.organizer,'EXECUTOR',Sync()):
            value={'title':'主题','intro':'说明','cards':[{'title':str(i),'body':'内容'} for i in range(3)],'caption':'发布正文','checks':'待核实'}
            with patch.object(creation.image_editorial,'request',return_value=(value,{'total_tokens':100})) as call:
                body=creation.Input(source='我的原稿')
                first=creation.start(body);second=creation.start(body)
                self.assertEqual(first['id'],second['id']);self.assertEqual(call.call_count,1)
                self.assertEqual(second['status'],'completed');self.assertEqual(body.source,'我的原稿')
                self.assertEqual(creation.read(first['id'])['result']['caption'],'发布正文')
    def test_malformed_output_rejected(self):
        for value in [{},{'cards':[]},{'cards':[{}]*9}]:
            with self.assertRaises(ValueError):creation.checked(value)
    def test_recovery(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(store,'DATA',Path(folder)),patch.object(store,'DB',Path(folder)/'tasks.sqlite3'):
            creation.save({'id':'fixture','status':'running'});creation.recover()
            self.assertEqual(creation.get('fixture')['status'],'failed')
