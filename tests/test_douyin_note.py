import json, sys, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
import articles
import image_documents
import pipeline
import store
import xhs_ingest

PNG = b'\x89PNG\r\n\x1a\nnote-fixture'
NOTE = 'https://www.douyin.com/note/7702009006068248037'


def page(index, text):
    return {'id': f'image-{index}', 'status': 'ok', 'width': 10, 'height': 10, 'version': 'fixture-v1', 'seconds': .1,
            'regions': [{'id': 'r1', 'text': text, 'score': .9, 'bbox': [0, 0, 10, 10]}]}


class NoteUrlTests(unittest.TestCase):
    def test_note_and_video_ids_with_kind(self):
        cases = [(NOTE, '7702009006068248037', 'note'),
                 ('https://www.iesdouyin.com/share/note/7702009006068248037/?a=b', '7702009006068248037', 'note'),
                 (NOTE + '?previous_page=app_code_link', '7702009006068248037', 'note'),
                 ('https://www.douyin.com/video/7692043092752338239', '7692043092752338239', 'video'),
                 ('https://www.iesdouyin.com/share/video/7692043092752338239/?a=b', '7692043092752338239', 'video'),
                 ('https://www.douyin.com/user/x?modal_id=7692043092752338239', '7692043092752338239', 'video')]
        for url, ident, kind in cases:
            with self.subTest(url=url):
                self.assertEqual(pipeline.id_from_url(url), ident)
                self.assertEqual(pipeline.kind_from_url(url), kind)

    def test_unrelated_paths_are_not_ids(self):
        for url in ['https://www.douyin.com/note/123', 'https://www.douyin.com/notes/7702009006068248037',
                    'https://www.douyin.com/user/7702009006068248037', 'https://www.douyin.com/video/1234567890123',
                    'https://www.douyin.com/note/12345678901234567890123']:
            with self.subTest(url=url):
                self.assertIsNone(pipeline.id_from_url(url))

    def test_short_link_resolves_note_kind(self):
        import httpx
        response = httpx.Response(302, headers={'Location': 'https://www.iesdouyin.com/share/note/7702009006068248037/?a=b'})
        with patch('pipeline.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value = response
            self.assertEqual(pipeline.resolve('https://v.douyin.com/abc/'), ('7702009006068248037', 'note'))
            self.assertEqual(client.return_value.__enter__.return_value.get.call_count, 1)
        with patch('pipeline.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value = response
            self.assertEqual(pipeline.resolve_id('https://v.douyin.com/abc/'), '7702009006068248037')

    def test_video_short_link_still_resolves_video(self):
        import httpx
        response = httpx.Response(302, headers={'Location': 'https://www.iesdouyin.com/share/video/7692043092752338239/?a=b'})
        with patch('pipeline.httpx.Client') as client:
            client.return_value.__enter__.return_value.get.return_value = response
            self.assertEqual(pipeline.resolve('https://v.douyin.com/abc/'), ('7692043092752338239', 'video'))

    def test_note_cdn_hosts_are_allowlisted(self):
        self.assertTrue(pipeline.media_host('https://p3-pc-sign.douyinpic.com/tos-cn-i/x.webp?a=1'))
        self.assertTrue(pipeline.media_host('https://p9-pc-sign.douyinpic.com/tos-cn-i/y.webp'))
        self.assertFalse(pipeline.media_host('https://douyinpic.com.evil.test/x.webp'))
        self.assertFalse(pipeline.media_host('http://p3-pc-sign.douyinpic.com/x.webp'))


class NoteTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ps = [patch.object(store, 'DATA', self.root), patch.object(store, 'DB', self.root/'tasks.sqlite3')]
        for p in self.ps: p.start()
        store.init()
        self.task = {'id': 'a'*16, 'url': NOTE, 'provider': 'local', 'language': 'zh', 'keep_media': True}
        self.directory = store.DATA/'jobs'/self.task['id']

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def payload(self, count=2):
        return {'status': 'ok', 'id': '7702009006068248037', 'title': '教程被举报后再发一次', 'author': '染',
                'create_time': 1700000000, 'tags': ['deepseek'],
                'images': [{'index': i, 'urls': [f'https://p3-pc-sign.douyinpic.com/x{i}.webp',
                                                 f'https://p9-pc-sign.douyinpic.com/y{i}.webp']} for i in range(count)],
                'total': count}

    def fake_ocr(self, ident):
        item = articles.get(ident)
        image_documents.commit_pages(ident, {'pages': [page(i+1, f'第{i+1}页文字') for i in range(item['expected_images'])]}, final=True)

    def run_note(self, payload=None, fetch=None, meta=None):
        updates = []
        with patch.object(pipeline, 'note_payload', return_value=payload or self.payload()), \
             patch.object(pipeline, 'get_metadata', side_effect=meta or RuntimeError('视频链不应被调用')), \
             patch.object(image_documents, 'run_ocr', side_effect=self.fake_ocr), \
             patch('article_fetch.fetch', side_effect=fetch or (lambda url, limit, referer='': (PNG+url[-8:].encode(), 'image/webp', url))):
            pipeline.run_task(self.task, lambda **kw: updates.append(kw))
        return updates

    def test_note_task_builds_text_document_without_audio_or_video(self):
        updates = self.run_note()
        result = json.loads((self.directory/'transcript.json').read_text(encoding='utf8'))
        self.assertEqual(result['engine'], 'image_ocr')
        self.assertEqual(result['images'], 2)
        self.assertEqual(result['source_url'], NOTE)
        self.assertIn('第1页文字', result['text'])
        self.assertIn('第2页文字', result['text'])
        self.assertTrue((self.directory/'transcript.md').exists())
        self.assertTrue((self.directory/'transcript.txt').exists())
        self.assertFalse((self.directory/'audio.wav').exists())
        self.assertFalse((self.directory/'original.mp4').exists())
        done = [f for f in updates if f.get('status') == 'completed']
        self.assertEqual(len(done), 1)
        self.assertTrue(any(f.get('media_kind') == 'note' for f in updates))
        self.assertTrue(any(f.get('video_id') == '7702009006068248037' for f in updates))
        self.assertFalse(done[0]['media_available'])
        self.assertTrue(any(f.get('message', '').startswith('正在保存图文原图') for f in updates))
        item = articles.get(json.loads((self.directory/'note-article.json').read_text(encoding='utf8'))['id'])
        self.assertEqual(item['expected_images'], 2)
        self.assertEqual(item['source_url'], NOTE)
        self.assertEqual(item['author'], '染')
        self.assertEqual(json.loads((self.directory/'source.json').read_text(encoding='utf8'))['detail']['author']['nickname'], '染')

    def test_note_retry_reuses_saved_pages_and_article(self):
        self.run_note()
        article = json.loads((self.directory/'note-article.json').read_text(encoding='utf8'))['id']
        calls = []
        with patch.object(pipeline, 'note_payload', return_value=self.payload()), \
             patch.object(image_documents, 'run_ocr', side_effect=self.fake_ocr), \
             patch('article_fetch.fetch', side_effect=lambda url, limit, referer='': calls.append(url) or (PNG+url[-8:].encode(), 'image/webp', url)):
            pipeline.run_task(self.task, lambda **kw: None)
        self.assertEqual(calls, [])
        self.assertEqual(json.loads((self.directory/'note-article.json').read_text(encoding='utf8'))['id'], article)

    def test_missing_image_fails_without_pretending_complete(self):
        with self.assertRaises(ValueError) as caught:
            self.run_note(fetch=lambda url, limit, referer='': (_ for _ in ()).throw(ValueError('图片下载失败')))
        self.assertIn('第1页图片获取失败', str(caught.exception))

    def test_image_post_with_no_images_is_rejected(self):
        payload = self.payload(); payload['images'] = []; payload['total'] = 0
        with self.assertRaises(RuntimeError) as caught:
            self.run_note(payload=payload)
        self.assertIn('没有可用的图文图片', str(caught.exception))

    def test_task_with_saved_video_id_keeps_video_route(self):
        self.task.update(video_id='7692043092752338239')
        self.task['url'] = 'https://www.douyin.com/video/7692043092752338239'
        with patch.object(pipeline, 'get_metadata', side_effect=RuntimeError('走了视频链')):
            with self.assertRaises(RuntimeError) as caught:
                pipeline.run_task(self.task, lambda **kw: None)
        self.assertIn('走了视频链', str(caught.exception))

    def test_worker_python_prefers_main_venv_only_when_no_isolated_env(self):
        self.root_join = self.root
        with patch.object(store, 'ROOT', self.root), patch('importlib.util.find_spec', return_value=object()):
            self.assertEqual(image_documents.worker_python(), Path(sys.executable))
        with patch.object(store, 'ROOT', self.root), patch('importlib.util.find_spec', return_value=None):
            with self.assertRaises(ValueError):
                image_documents.worker_python()


class XhsImageRegressionTests(unittest.TestCase):
    """小红书图文与小芬图集共用 to_document 后仍产出一致结构。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ps = [patch.object(store, 'DATA', self.root), patch.object(store, 'DB', self.root/'tasks.sqlite3')]
        for p in self.ps: p.start()
        store.init()

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def test_xhs_image_note_still_yields_ocr_text(self):
        card = {'type': 'normal', 'title': '小红书图文标题', 'desc': '作者文案',
                'user': {'user_id': 'u1', 'nickname': '作者'},
                'image_list': [{'url_default': 'https://sns-img.xhscdn.com/a.webp'},
                               {'info_list': [{'url': 'https://sns-img.xhscdn.com/b.webp'}]}]}
        task = {'id': 'b'*16, 'url': 'https://www.xiaohongshu.com/explore/abcdefabcdefabcdefabcdef', 'language': 'zh'}
        directory = store.DATA/'jobs'/task['id']; directory.mkdir(parents=True)
        metadata = {}
        updates = []

        def ocr(ident):
            item = articles.get(ident)
            image_documents.commit_pages(ident, {'pages': [page(i+1, f'图文第{i+1}页') for i in range(item['expected_images'])]}, final=True)

        with patch.object(xhs_ingest, 'detail', return_value=('abcdefabcdefabcdefabcdef', card)), \
             patch.object(image_documents, 'run_ocr', side_effect=ocr), \
             patch('article_fetch.fetch', side_effect=lambda url, limit, referer='': (PNG+url[-6:].encode(), 'image/webp', url)):
            result = xhs_ingest.ingest(task, lambda **kw: updates.append(kw), directory, metadata)
        self.assertEqual(result['engine'], 'image_ocr')
        self.assertIn('图文第1页', result['text'])
        self.assertIn('图文第2页', result['text'])
        self.assertEqual(metadata['article_id'], result.get('article_id', metadata['article_id']))
        self.assertEqual(articles.get(metadata['article_id'])['expected_images'], 2)
        self.assertTrue(any(f.get('stage') == 'transcribing' for f in updates))


class WebAndBatchEntryTests(unittest.TestCase):
    """Web 工作台与批量输入都走同一个 prepare，note 链接应被识别为 douyin 条目。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ps = [patch.object(store, 'DATA', self.root), patch.object(store, 'DB', self.root/'tasks.sqlite3')]
        for p in self.ps: p.start()
        store.init()

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def test_web_link_endpoint_accepts_note_url(self):
        import app, link_jobs
        from fastapi.testclient import TestClient
        with TestClient(app.app) as client, \
             patch.object(link_jobs, 'submit', return_value={'id': 'job', 'task_id': 'task', 'status': 'queued'}) as submit:
            response = client.post('/api/link', json={'url': NOTE, 'language': 'zh'})
        self.assertEqual(response.status_code, 200, response.text)
        plan = submit.call_args.args[1]
        self.assertEqual(plan['kind'], 'douyin')
        self.assertRegex(plan['ident'], r'^[a-f0-9]{16}$')

    def test_batch_preview_lists_note_link_as_waiting(self):
        import app
        from fastapi.testclient import TestClient
        rows = [{'text': NOTE, 'episode': None, 'summarize': False, 'feed_seq': None}]
        with TestClient(app.app) as client:
            response = client.post('/api/link-batches/preview', json={'rows': rows, 'language': 'zh'})
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()['items'][0]
        self.assertEqual(item['status'], 'waiting')
        self.assertEqual(item['platform'], 'douyin')
        self.assertRegex(item['task_id'], r'^[a-f0-9]{16}$')

    def test_video_url_keeps_video_identity(self):
        args = type('A', (), {'url': 'https://www.douyin.com/video/7685395900839038248', 'language': 'zh',
                              'episode': None, 'episode_id': None, 'episode_guid': None})()
        plan = __import__('link_ingest').prepare(args)
        self.assertEqual(plan['kind'], 'douyin')
        self.assertRegex(plan['ident'], r'^[a-f0-9]{16}$')


if __name__ == '__main__':
    unittest.main()
