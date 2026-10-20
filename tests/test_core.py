import json
import queue
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import settings
import store
from fastapi.testclient import TestClient
from pipeline import id_from_url, input_url, media_host, resolve_id


class InputSafetyTests(unittest.TestCase):
    def test_full_share_text(self):
        url = input_url('0.07 复制打开抖音 https://v.douyin.com/Dv4LnzQVp8E/ 看作品')
        self.assertEqual(url, 'https://v.douyin.com/Dv4LnzQVp8E/')

    def test_only_douyin_https(self):
        for url in ['http://127.0.0.1/', 'https://douyin.com.evil.test/video/123', 'https://user@evil.test/', 'http://v.douyin.com/a/', 'https://www.douyin.com:8000/video/123']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                input_url(url)

    def test_video_id_and_modal(self):
        self.assertEqual(id_from_url('https://www.douyin.com/video/7692043092752338239'), '7692043092752338239')
        self.assertEqual(id_from_url('https://www.douyin.com/user/test?modal_id=7692043092752338239'), '7692043092752338239')

    def test_media_allowlist(self):
        self.assertTrue(media_host('https://v3.douyinvod.com/a.mp4'))
        self.assertFalse(media_host('https://douyinvod.com.evil.test/a'))
        self.assertFalse(media_host('http://localhost/a'))
        self.assertFalse(media_host('https://127.0.0.1/a'))

    def test_stops_after_id_redirect(self):
        import httpx
        response = httpx.Response(302, headers={'Location':'https://www.iesdouyin.com/share/video/7692043092752338239/?a=b'})
        with patch('pipeline.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value = response
            self.assertEqual(resolve_id('https://v.douyin.com/abc/'), '7692043092752338239')
            self.assertEqual(client.return_value.__enter__.return_value.get.call_count, 1)


class PersistenceAndApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        directory = Path(self.temp.name)
        self.patches = [patch.object(store, 'DATA', directory), patch.object(store, 'DB', directory/'tasks.sqlite3'),
                        patch.object(settings, 'FILE', directory/'settings.json'), patch.object(app, 'TASKS', queue.Queue())]
        for p in self.patches: p.start()
        store.init()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()

    def test_storage_survives_connection_reopen(self):
        record = {'id':'1234567890abcdef','status':'queued','created_at':time.time(),'title':'中文测试'}
        store.save(record)
        store.init()
        self.assertEqual(store.get(record['id'])['title'], '中文测试')

    def test_api_validation_origin_duplicate_and_retry(self):
        with TestClient(app.app) as client:
            # No external network is used: stop the fake worker at a deterministic error.
            with patch.object(app, 'run_task', side_effect=RuntimeError('测试用中断，已保存片段')):
                self.assertEqual(client.post('/api/tasks',json={'share_text':'https://evil.test'}).status_code,400)
                self.assertEqual(client.post('/api/tasks',headers={'Origin':'https://evil.test'},json={'share_text':'https://v.douyin.com/abc/'}).status_code,403)
                response = client.post('/api/tasks',json={'share_text':'https://v.douyin.com/abc/','provider':'local'})
                self.assertEqual(response.status_code,200)
                task_id = response.json()['id']
                for _ in range(50):
                    task = client.get('/api/tasks/'+task_id).json()
                    if task['status'] == 'failed': break
                    time.sleep(.02)
                self.assertEqual(task['status'],'failed')
                duplicate = client.post('/api/tasks',json={'share_text':'https://v.douyin.com/abc/'}).json()
                self.assertTrue(duplicate['cached'])
                self.assertEqual(client.post('/api/tasks/'+task_id+'/retry').status_code,200)
                app.TASKS.join()
            self.assertEqual(client.get('/api/tasks/invalid').status_code,404)
            self.assertEqual(client.get('/api/tasks/'+task_id+'/export/txt').status_code,404)

    def test_restart_recovers_incomplete_task(self):
        task = {'id':'1234567890abcdef','url':'https://v.douyin.com/test/','provider':'local','status':'running','created_at':time.time()}
        store.save(task)
        def finish(record, update, key):
            update(status='completed', message='恢复成功')
        with patch.object(app, 'run_task', side_effect=finish):
            with TestClient(app.app) as client:
                app.TASKS.join()
                result = client.get('/api/tasks/'+task['id']).json()
                self.assertEqual(result['status'],'completed')

    def test_batch_pause_resume_and_origin(self):
        parent_id, child_id = 'aaaaaaaaaaaaaaaa', 'bbbbbbbbbbbbbbbb'
        store.save({'id': parent_id, 'kind': 'creator', 'status': 'processing', 'paused': True,
                    'created_at': time.time(), 'children': [child_id], 'provider': 'local'})
        store.save({'id': child_id, 'parent_id': parent_id, 'status': 'queued',
                    'created_at': time.time(), 'provider': 'local'})
        with patch.object(app, 'run_task', side_effect=lambda task, update, key: update(status='completed')) as run:
            with TestClient(app.app) as client:
                app.TASKS.join()
                self.assertEqual(store.get(child_id)['status'], 'paused')
                run.assert_not_called()
                self.assertEqual(client.post('/api/batches/'+parent_id+'/resume', headers={'Origin':'https://evil.test'}).status_code, 403)
                self.assertEqual(client.post('/api/batches/'+parent_id+'/resume').status_code, 200)
                app.TASKS.join()
                self.assertEqual(store.get(child_id)['status'], 'completed')
                self.assertEqual(client.get('/api/tasks/'+parent_id).json()['counts']['completed'], 1)

    def test_dpapi_and_no_key_disclosure(self):
        key = 'test-only-not-a-real-key'
        settings.save('cloud',key)
        self.assertEqual(settings.cloud_key(),key)
        self.assertNotIn(key,settings.FILE.read_text(encoding='utf-8'))
        with TestClient(app.app) as client:
            response = client.get('/api/settings')
            self.assertTrue(response.json()['key_configured'])
            self.assertNotIn(key,response.text)
            self.assertNotIn('encrypted_key',response.text)


if __name__ == '__main__':
    unittest.main()
