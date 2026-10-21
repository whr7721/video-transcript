import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import discovery as d
import store


def candidate(ident='1234567890123456789', **fields):
    return dict(video_id=ident, canonical_url=f'https://www.douyin.com/video/{ident}',
                caption='AI客户交付案例', author_name='测试作者', author_id=None,
                published_at=None, metadata_checked_at='2026-10-21', duration_sec=85,
                media_type='video', matched_queries=['AI 接单'], digg_count=3, **fields)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(store, 'DATA', root), patch.object(store, 'DB', root/'tasks.db'),
                        patch.object(d.EXECUTOR, 'submit')]
        for p in self.patches: p.start()
        store.init()
        self.client = TestClient(app.app)

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def job(self):
        result = d.start(d.Search(topic='AI工具的实际变现', queries=['AI 接单'], max_candidates_total=10))
        return d.get(result['id'])

    def payload(self, value, **fields):
        result = dict(schema_version=1, request_id=value['id'], status='ok', items=[candidate()],
                      warnings=[], per_query_progress=[], resume_token='opaque-token', stopped_reason='target_reached')
        result.update(fields)
        return result

    def invoke(self, payload):
        def run(request, output):
            data = json.loads(request.read_text(encoding='utf-8'))
            self.assertTrue(data['metadata_only'])
            self.assertEqual(data['channel'], 'video')
            output.write_text(json.dumps(payload), encoding='utf-8')
            return False
        return run

    def test_contract_metadata_only_and_no_media_or_model_calls(self):
        value = self.job()
        with patch.object(d, 'invoke', side_effect=self.invoke(self.payload(value))), \
             patch.object(app, 'run_task') as asr, patch.object(app.TASKS, 'put') as download:
            d.run(value['id'])
        after = d.public(d.get(value['id']))
        self.assertEqual(after['state'], 'finished')
        self.assertEqual(after['items'][0]['video_id'], candidate()['video_id'])
        self.assertNotIn('resume_token', after)
        self.assertNotIn('resume_token', after['request'])
        self.assertTrue(after['can_resume'])
        asr.assert_not_called(); download.assert_not_called()

    def test_selection_cas_unknown_ids_and_no_passive_transcript_changes(self):
        value = self.job(); value.update(state='finished', items=[candidate()]); d.save(value)
        store.save(dict(id='old-task', video_id=candidate()['video_id'], status='completed', created_at=1,
                        result={'text':'原话不能变'}, kind='single'))
        before = store.get('old-task')
        saved = d.select(value['id'], 1, [candidate()['video_id']])
        self.assertEqual(saved['items'][0]['transcript_id'], 'old-task')
        self.assertEqual(store.get('old-task'), before)
        with self.assertRaises(RuntimeError): d.select(value['id'], 1, [])
        with self.assertRaises(ValueError): d.select(value['id'], 2, ['9999999999999999999'])
        self.assertEqual(d.get(value['id'])['selected_ids'], [candidate()['video_id']])

    def test_failed_resume_keeps_candidates_token_and_selection(self):
        value = self.job()
        value.update(state='finished', items=[candidate()], resume_token='opaque-token', selected_ids=[candidate()['video_id']])
        d.save(value)
        d.resume(value['id'], 30)
        result = dict(schema_version=1, status='error', stopped_reason='startup_error', items=[], warnings=['启动失败'])
        with patch.object(d, 'invoke', side_effect=self.invoke(result)): d.run(value['id'])
        after = d.get(value['id'])
        self.assertEqual(len(after['items']), 1)
        self.assertEqual(after['resume_token'], 'opaque-token')
        self.assertEqual(after['selected_ids'], value['selected_ids'])
        self.assertEqual(after['adapter_status'], 'error')
        d.resume(value['id'], 30)
        restored = json.loads((store.DATA/'discovery'/value['id']/'result.json').read_text(encoding='utf-8'))
        self.assertEqual(restored['items'], value['items'])

    def test_timeout_keeps_atomic_partial_output(self):
        value = self.job()
        def timeout(request, output):
            self.invoke(self.payload(value, status='partial'))(request, output)
            return True
        with patch.object(d, 'invoke', side_effect=timeout): d.run(value['id'])
        after = d.get(value['id'])
        self.assertEqual(after['adapter_status'], 'partial')
        self.assertEqual(len(after['items']), 1)

    def test_recover_never_automatically_restarts_search(self):
        value = self.job(); d.EXECUTOR.submit.reset_mock(); d.recover()
        self.assertEqual(d.get(value['id'])['state'], 'interrupted')
        d.EXECUTOR.submit.assert_not_called()

    def test_recover_reads_partial_checkpoint_without_network(self):
        value = self.job()
        path = store.DATA/'discovery'/value['id']/'result.json'
        store.atomic_json(path, self.payload(value, status='partial'))
        d.EXECUTOR.submit.reset_mock(); d.recover()
        restored = d.get(value['id'])
        self.assertEqual(restored['state'], 'interrupted')
        self.assertEqual(len(restored['items']), 1)
        self.assertEqual(restored['resume_token'], 'opaque-token')
        d.EXECUTOR.submit.assert_not_called()

    def test_invalid_or_cross_request_output_rejected(self):
        value = self.job()
        for fields in [dict(schema_version=2), dict(request_id='wrong'), dict(status='mystery'), dict(items=[{'video_id':'x'}])]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                d.validate_result(self.payload(value, **fields), value)
        raw = self.payload(value)
        raw['items'][0]['canonical_url'] = 'javascript:alert(1)'
        with self.assertRaises(ValueError): d.validate_result(raw, value)

    def test_unknown_duration_is_not_silently_zero(self):
        value = self.job()
        for duration in [None, -1, True, float('nan'), '100']:
            raw = self.payload(value);raw['items'][0]['duration_sec'] = duration
            self.assertIsNone(d.validate_result(raw, value)['items'][0]['duration_sec'])

    def test_malformed_progress_and_non_video_selection_are_rejected(self):
        value = self.job()
        raw = self.payload(value, per_query_progress=[dict(query='AI 接单',pages={'bad':1},exhausted=False)])
        with self.assertRaises(ValueError): d.validate_result(raw, value)
        image = candidate(); image['media_type'] = 'image'
        value.update(state='finished', items=[image]); d.save(value)
        with self.assertRaises(ValueError): d.select(value['id'], 1, [image['video_id']])

    def test_dedup_and_queries_validation(self):
        value = self.job()
        raw = self.payload(value); raw['items'] *= 2
        self.assertEqual(len(d.validate_result(raw, value)['items']), 1)
        raw['items'][0]['matched_queries'] = ['other']
        with self.assertRaises(ValueError): d.validate_result(raw, value)

    def test_selection_during_search_survives_final_merge(self):
        value = self.job();value.update(items=[candidate()]);d.save(value)
        def output(request, path):
            d.select(value['id'], 1, [candidate()['video_id']])
            return self.invoke(self.payload(value))(request, path)
        with patch.object(d, 'invoke', side_effect=output): d.run(value['id'])
        self.assertEqual(d.get(value['id'])['selection_revision'], 2)
        self.assertEqual(d.get(value['id'])['selected_ids'], [candidate()['video_id']])

    def test_api_input_busy_and_cross_site(self):
        self.assertEqual(self.client.post('/api/discovery', json={'topic':'x','queries':['x']*4}).status_code, 422)
        self.assertEqual(self.client.post('/api/discovery', json={'topic':' ','queries':['x']}).status_code, 400)
        self.assertEqual(self.client.post('/api/discovery', json={'topic':'x','queries':['x']}, headers={'Origin':'https://evil.test'}).status_code, 403)
        value = self.job()
        self.assertEqual(self.client.post('/api/discovery', json={'topic':'x','queries':['x']}).status_code, 409)
        self.assertEqual(self.client.get('/api/discovery/not-valid').status_code, 404)
        self.assertNotIn('resume_token', self.client.get('/api/discovery/'+value['id']).json())

    def test_existing_adapter_sample_shape_matches_without_saving_content(self):
        # Synthetic fixtures above cover failure states; local delivered sample
        # is optional and never copied into source control.
        path = Path(r'D:\zcode1\douyin-discovery\samples\result-sample.json')
        if not path.exists(): self.skipTest('local adapter sample not installed')
        raw = json.loads(path.read_text(encoding='utf-8'))
        value = self.job(); value['request']['queries'] = ['AI工具 变现 实操']; raw['request_id'] = value['id']
        self.assertEqual(len(d.validate_result(raw, value)['items']), 20)


if __name__ == '__main__': unittest.main()
