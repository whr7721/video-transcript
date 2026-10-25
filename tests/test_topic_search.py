import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import documents
import research
import store
import topic_search as search


class TopicSearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(store, 'DATA', root), patch.object(store, 'DB', root/'test.sqlite3')]
        for p in self.patches:p.start()
        store.init()
        self.task = {'id': 'a'*16, 'status': 'completed', 'title': '工具案例',
                     'result': {'segments': [{'text': '🙂公开过程吸引客户，AI工具需要真实交付。', 'start': 1, 'end': 5},
                                             {'text': '第二段记录缓存命中。', 'start': 6, 'end': 9}]}}
        store.save(self.task)
        with store.connect() as db:
            research.init(db)
            db.execute("INSERT INTO research_topics VALUES ('one','第一专题',0),('two','另一专题',0)")
        self.note('n1')

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def note(self, ident, topic='one', personal='我想用AI工具交付', basis='original'):
        job = {'id': ident, 'task_id': self.task['id'], 'title': self.task['title'],
               'context': {'basis': basis, 'version': 'old-version', 'selection': '公开过程吸引客户'},
               'sections': [{'text': '不应索引的AI幻觉独占词'}]}
        with store.connect() as db:
            db.execute('INSERT INTO research_jobs VALUES (?,?)', (ident, json.dumps(job, ensure_ascii=False)))
            db.execute('INSERT INTO research_notes VALUES (?,?,?,?,?,?,?)', (ident, topic, ident, personal, 1, 0, 0))

    def snapshot(self):
        with store.connect() as db:
            return {t: [tuple(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY 1')] for t in ('tasks', 'research_notes', 'research_jobs', 'research_topics')}

    def test_scope_dedup_and_no_source_mutation(self):
        self.note('n2');self.note('other', 'two', '秘密记录隔离')
        before = self.snapshot()
        result = search.search('one', '交付')
        self.assertEqual(result['scope'], {'personal': 2, 'selection': 2, 'original': 1})
        self.assertEqual(len([r for r in result['items'] if r['category']=='original']), 1)
        self.assertFalse(search.search('one', '秘密')['items'])
        self.assertFalse(search.search('one', '幻觉独占词')['items'])
        self.assertEqual(before, self.snapshot())

    def test_more_than_200_notes_and_filter_before_limit(self):
        for i in range(205):self.note('extra'+str(i), personal='公开过程')
        self.note('last', personal='隐藏针叶独特词')
        self.assertTrue(search.search('one', '针叶', 'personal')['items'])
        result = search.search('one', '公开过程', 'original')
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['category'], 'original')
        self.assertTrue(search.search('one', '公开过程', 'selection')['truncated'])

    def test_live_updates_removal_rebuild_and_stale_reference(self):
        old = search.search('one', '交付', 'personal')['items'][0]
        research.update_note('n1', 1, '新词柠檬树')
        with self.assertRaises(documents.Conflict):search.context('one', old['hit_id'], old['source_hash'])
        self.assertFalse(search.search('one', '交付', 'personal')['items'])
        self.assertTrue(search.search('one', '柠檬', 'personal')['items'])
        with store.connect() as db:
            db.execute('DROP TABLE topic_search_fts');db.execute('DROP TABLE topic_search_passages');db.execute('DROP TABLE topic_search_state')
        self.assertTrue(search.search('one', '柠檬')['items'])
        with store.connect() as db:db.execute("UPDATE research_notes SET topic_id='two' WHERE id='n1'")
        self.assertFalse(search.search('one', '柠檬')['items'])

    def test_context_offsets_unicode_and_original_change(self):
        self.task['result']['segments'][0]['text'] = '🙂'*503+'缓存'*260
        store.save(self.task)
        result = search.search('one', '缓存', 'original')
        self.assertGreater(len(result['items']), 1)
        for hit in result['items']:
            ctx = search.context('one', hit['hit_id'], hit['source_hash'])
            self.assertTrue(all(ctx['blocks'][0]['text'][a:b] for a,b in ctx['blocks'][0]['highlights']))
            for a,b in hit['highlights']:self.assertIn('缓存', hit['text'][a:b])
        old = result['items'][0]
        self.task['result']['segments'][0]['text'] = '原文改变'
        store.save(self.task)
        with self.assertRaises(documents.Conflict):search.context('one', old['hit_id'], old['source_hash'])

    def test_missing_job_source_and_saved_basis_are_honest(self):
        self.note('draft', basis='draft')
        with store.connect() as db:
            db.execute('DELETE FROM tasks');db.execute("DELETE FROM research_jobs WHERE id='n1'")
        result = search.search('one', '公开过程')
        self.assertTrue(result['warnings'])
        self.assertEqual(result['items'][0]['basis'], 'draft')
        self.assertEqual(result['items'][0]['version'], 'old-version')

    def test_query_data_highlights_and_title_only(self):
        self.assertTrue(search.search('one', '缓')['items'])
        for query in ['交付 OR " * NOT % _', 'ＡＩ', '🙂', '"']:
            search.search('one', query)
        self.assertEqual(search.marks('🙂ＡＩ工具', ['ai']), [[1,3]])
        result = search.search('one', '案例')
        self.assertTrue(result['title_matches'])
        self.assertFalse(result['items'])
        title=result['title_matches'][0]
        self.assertEqual(search.context('one',title['hit_id'],title['source_hash'])['uid'],title['uid'])
        with self.assertRaises(ValueError):search.search('one', ' ')
        with self.assertRaises(LookupError):search.search('unknown', '交付')

    def test_api_contract_without_key_and_stale_context(self):
        client = TestClient(app.app)
        response = client.get('/api/studio/research/topics/one/search', params={'q':'交付'})
        self.assertEqual(response.status_code, 200)
        hit = response.json()['items'][0]
        url = '/api/studio/research/topics/one/search/context'
        self.assertEqual(client.post(url, json={k:hit[k] for k in ('hit_id','source_hash')}).status_code, 200)
        self.assertEqual(client.get('/api/studio/research/topics/one/search?q=a&category=other').status_code, 422)
        with patch.object(search, 'search', side_effect=__import__('sqlite3').OperationalError('locked')):
            self.assertEqual(client.get('/api/studio/research/topics/one/search?q=交付').status_code, 503)

    def test_production_tokens_match_frozen_baseline(self):
        from experiments.retrieval import baselines
        for text in ['普通人如何用AI', 'ＡＩ与CodeBuddy', '🙂这是一个测试', '缓存 缓存']:
            self.assertEqual(search.terms(text, False), baselines.terms(text, 2, unique=False))
