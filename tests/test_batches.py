import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import batches
import store
import pipeline
from batch_rules import classify_post


class BatchTests(unittest.TestCase):
    def test_successful_media_waits_for_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            task = {'id': '0123456789abcdef', 'video_id': '7692820343819455785', 'url': '', 'provider': 'local', 'keep_media': False, 'max_duration_sec': 600}
            metadata = {'detail': {'desc': '测试', 'author': {'nickname': '测试'}}, 'urls': []}
            def download(urls, target, progress):
                target.write_bytes(b'owned video')
            def audio(video, target):
                target.write_bytes(b'owned audio')
            updates = []
            historical = root/'old-video.mp4'; historical.write_bytes(b'history')
            with patch.object(store,'DATA',root/'data'),patch.object(store,'DB',root/'data'/'tasks.sqlite3'),patch.object(pipeline, 'ROOT', root), patch.object(pipeline, 'get_metadata', return_value=metadata), patch.object(pipeline, 'download_video', side_effect=download), patch.object(pipeline, 'probe_media', return_value=120), patch.object(pipeline, 'extract_audio', side_effect=audio), patch('transcribe.local_transcribe', return_value={'text': '原话', 'segments': []}):
                store.init()
                pipeline.run_task(task, lambda **kw: updates.append(kw))
            directory = root/'data'/'jobs'/task['id']
            self.assertTrue((directory/'transcript.txt').exists())
            self.assertTrue((directory/'original.mp4').exists())
            self.assertTrue((directory/'audio.wav').exists())
            self.assertTrue(historical.exists())
            self.assertEqual(updates[-1]['status'], 'completed')
            self.assertTrue(updates[-1]['media_available'])

    def test_duration_boundary_and_images(self):
        item = {'aweme_id': '7692820343819455785', 'video': {'duration': 600000}}
        self.assertEqual(classify_post(item), ('eligible', 600))
        item['video']['duration'] = 600001
        self.assertEqual(classify_post(item)[0], 'too_long')
        item['video']['duration'] = 0
        self.assertEqual(classify_post(item)[0], 'unknown')
        item['images'] = [{}]
        self.assertEqual(classify_post(item)[0], 'image')

    def test_all_three_duration_limits(self):
        for maximum in (600, 1200, 1800):
            for actual, expected in ((maximum*1000, 'eligible'), (maximum*1000+1, 'too_long')):
                item = {'aweme_id': '7692820343819455785', 'video': {'duration': actual}}
                self.assertEqual(classify_post(item, maximum)[0], expected)

    def test_api_duration_default_and_validation(self):
        from app import NewBatch
        from pydantic import ValidationError
        self.assertEqual(NewBatch(share_text='link').max_duration_sec, 600)
        for maximum in (600, 1200, 1800):
            self.assertEqual(NewBatch(share_text='link', max_duration_sec=maximum).max_duration_sec, maximum)
        with self.assertRaises(ValidationError):
            NewBatch(share_text='link', max_duration_sec=3600)

    def test_discovery_dedup_continuation_and_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(store, 'DATA', root/'data'), patch.object(store, 'DB', root/'data'/'tasks.sqlite3'), patch.object(batches, 'ROOT', root), patch.object(batches, 'prepare_session'), patch.object(batches.subprocess, 'run'):
                store.init()
                task = {'id': '0123456789abcdef', 'kind': 'creator', 'url': 'https://www.douyin.com/user/abcdefghijk', 'author': '测试', 'provider': 'local', 'limit': 1, 'max_duration_sec': 1200, 'status': 'queued', 'created_at': time.time()}
                store.save(task)
                directory = root/'data'/'batches'/task['id']
                directory.mkdir(parents=True)
                posts = [{'aweme_id': str(7692820343819455785+i), 'desc': f'视频{i}', 'video': {'duration': 900000+i*100000}, 'author': {'sec_uid': 'abcdefghijk'}} for i in range(2)]
                store.atomic_json(directory/'listing.json', {'status': 'ok', 'posts': posts, 'sources': {}, 'has_more': False, 'scan_complete': True})
                def update(**fields):
                    current = store.get(task['id']); current.update(fields); store.save(current)
                queued = []
                batches.run_creator(task, update, queued.append)
                current = store.get(task['id'])
                self.assertEqual(len(queued), 1)
                self.assertTrue(current['has_more'])
                child = store.get(queued[0]); child.update(status='completed'); store.save(child)
                self.assertEqual(child['max_duration_sec'], 1200)
                doc = root/'data'/'jobs'/child['id']; doc.mkdir(parents=True)
                (doc/'transcript.txt').write_text('原话', encoding='utf-8')
                current['limit'] = 2
                batches.run_creator(current, update, queued.append)
                current = store.get(task['id'])
                self.assertEqual(len(current['children']), 2)
                self.assertEqual(len(queued), 2)
                self.assertFalse(current['has_more'])
                second = store.get(queued[-1]); second['status'] = 'failed'; store.save(second)
                self.assertEqual(batches.reconcile(current)['status'], 'partial')
                with zipfile.ZipFile(io.BytesIO(batches.export_zip(current))) as archive:
                    self.assertIn(f"{child['video_id']}.txt", archive.namelist())
                    self.assertEqual(json.loads(archive.read('批次索引.json'))['counts']['failed'], 1)


if __name__ == '__main__':
    unittest.main()
