"""四处 retry 的行为回归：状态守卫、重置字段、入队只发生一次；共用 job_retry.requeue 后保持不变。"""
import queue, tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import articles, image_documents, job_retry
import local_files as files
import podcasts, private_images, store


class LocalFileRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.tasks = queue.Queue()
        self.ps = [patch.object(store, 'DATA', root), patch.object(store, 'DB', root/'tasks.sqlite3'),
                   patch.object(files, 'TASKS', self.tasks), patch.object(files, 'UPLOAD_SLOT', threading.Lock())]
        for p in self.ps: p.start()
        store.init(); files.init()
        app = FastAPI(); app.include_router(files.router); self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def test_failed_task_requeues_and_keeps_media_flags(self):
        ident = 'a'*16
        store.save({'id': ident, 'source': {'kind': 'local_file'}, 'status': 'failed', 'stage': 'failed',
                    'error': '中断', 'message': '失败', 'keep_media': False, 'created_at': time.time()})
        self.assertEqual(self.client.post(f'/api/files/tasks/{ident}/retry').json(), {'id': ident})
        value = store.get(ident)
        self.assertEqual((value['status'], value['stage']), ('queued', 'queued'))
        self.assertIsNone(value['error'])
        self.assertIn('复用已完成语音片段', value['message'])
        self.assertFalse(value['keep_media'])
        self.assertEqual(self.tasks.get_nowait(), ident)

    def test_other_statuses_and_missing_ids_are_refused(self):
        ident = 'b'*16
        store.save({'id': ident, 'source': {'kind': 'local_file'}, 'status': 'completed', 'created_at': time.time()})
        self.assertEqual(self.client.post(f'/api/files/tasks/{ident}/retry').status_code, 409)
        self.assertEqual(self.client.post('/api/files/tasks/' + 'c'*16 + '/retry').status_code, 404)
        self.assertTrue(self.tasks.empty())


class PodcastRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.tasks = queue.Queue()
        self.ps = [patch.object(store, 'DATA', root), patch.object(store, 'DB', root/'tasks.sqlite3'),
                   patch.object(files, 'TASKS', self.tasks), patch.object(podcasts, 'EVENTS', {})]
        for p in self.ps: p.start()
        store.init(); files.init(); podcasts.init()
        app = FastAPI(); app.include_router(podcasts.router); self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def test_interrupted_import_resets_progress_and_requeues(self):
        ident = 'd'*16
        podcasts.save('podcast_imports', {'id': ident, 'status': 'interrupted', 'stage': 'running',
                                          'bytes': 987654, 'error': '中断', 'message': '停住'})
        value = self.client.post(f'/api/podcasts/imports/{ident}/retry').json()
        self.assertEqual((value['status'], value['stage'], value['bytes']), ('queued', 'queued', 0))
        self.assertIsNone(value['error'])
        self.assertEqual(self.tasks.get_nowait(), 'podcast:' + ident)

    def test_finished_import_is_not_retried(self):
        ident = 'e'*16
        podcasts.save('podcast_imports', {'id': ident, 'status': 'done'})
        self.assertEqual(self.client.post(f'/api/podcasts/imports/{ident}/retry').status_code, 409)
        self.assertTrue(self.tasks.empty())


class ImagePostRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.ps = [patch.object(store, 'DATA', root), patch.object(store, 'DB', root/'tasks.sqlite3')]
        for p in self.ps: p.start()
        store.init()
        app = FastAPI(); app.include_router(private_images.router); self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def test_partial_image_post_restarts_fetch(self):
        item = image_documents.create('图集', 1)
        image_documents.update(item['id'], source_share='https://www.douyin.com/note/7702009006068248037',
                               image_status='failed', status='ready', error='缺图')
        with patch.object(articles, 'EXECUTOR') as executor:
            response = self.client.post(f'/api/private/image-posts/{item["id"]}/retry')
        self.assertEqual(response.status_code, 200)
        current = articles.get(item['id'])
        self.assertEqual((current['image_status'], current['status']), ('fetching', 'running'))
        self.assertIsNone(current['error'])
        executor.submit.assert_called_once()
        self.assertEqual(executor.submit.call_args.args[1], item['id'])

    def test_missing_share_or_finished_post_is_refused(self):
        item = image_documents.create('图集', 1)
        self.assertEqual(self.client.post(f'/api/private/image-posts/{item["id"]}/retry').status_code, 404)
        image_documents.update(item['id'], source_share='https://www.douyin.com/note/7702009006068248037', image_status='completed')
        self.assertEqual(self.client.post(f'/api/private/image-posts/{item["id"]}/retry').status_code, 409)


class SharedHelperTests(unittest.TestCase):
    def test_requeue_resets_error_saves_once_and_enqueues_once(self):
        record = {'status': 'failed', 'error': 'boom', 'keep': 'keep'}
        saved, queued = [], []
        job_retry.requeue(record, saved.append, lambda: queued.append(1), status='queued', stage='queued')
        self.assertIsNone(record['error'])
        self.assertEqual((record['status'], record['stage'], record['keep']), ('queued', 'queued', 'keep'))
        self.assertEqual((saved, queued), ([record], [1]))


if __name__ == '__main__':
    unittest.main()
