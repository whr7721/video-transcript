import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import articles
import documents
import research
import store
import topic_search
import ocr_reading as reading
import ocr_evaluation as evaluation


def fixture():
    return {'id': 'sample', 'title': 'sample', 'kind': 'images', 'blocks': [
        {'id': 'image-1', 'type': 'image', 'text': '', 'page': 1, 'height': 1000, 'width': 500,
         'ocr_original': {'a': {'text': '原始OCR错宇', 'score': .99, 'bbox': [10, 200, 400, 240]},
                          'b': {'text': '12:33', 'score': .99, 'bbox': [1, 1, 50, 30]},
                          'c': {'text': 'MCP', 'score': .8, 'bbox': [10, 300, 200, 340]}}},
        *[{'id': 'image-1-'+r, 'type': 'ocr', 'text': t, 'source_image_id': 'image-1', 'region_id': r,
           'revision': 2, 'corrected': r == 'a'} for r, t in [('a', '人工校对正确字'), ('b', '12:33'), ('c', 'MCP')]]]}


class ReadingTests(unittest.TestCase):
    def test_original_copy_and_rules_do_not_mutate(self):
        item = fixture(); before = copy.deepcopy(item)
        rows = reading.selection(item)
        self.assertEqual([r['state'] for r in rows], ['keep', 'exclude', 'fold'])
        self.assertEqual(reading.blocks(item)[0]['text'], '原始OCR错宇')
        self.assertEqual(item, before)

    def test_ai_cannot_return_words_or_unknown_ids_or_omit_regions(self):
        rows = reading.rules(fixture())[:1]
        for value in [{'decisions': [{'id': rows[0]['id'], 'category': 'body', 'text': '改写'}]},
                      {'decisions': [{'id': 'other', 'category': 'body'}]}, {'decisions': []}]:
            with self.assertRaises(ValueError): reading.checked_ai(value, rows)
        self.assertEqual(reading.checked_ai({'decisions': [{'id': rows[0]['id'], 'category': 'body'}]}, rows)[rows[0]['id']]['source_key'], rows[0]['source_key'])

    def test_manual_override_and_source_change_expiration(self):
        item = fixture(); row = reading.rules(item)[2]
        item['reading_selection'] = {'manual': {row['id']: {'category': 'body', 'state': 'keep', 'source_key': row['source_key']}}}
        self.assertEqual(reading.selection(item)[2]['state'], 'keep')
        item['blocks'][0]['ocr_original']['c']['text'] = 'new'
        self.assertEqual(reading.selection(item)[2]['state'], 'fold')

    def test_page_split_and_no_unconfirmed_accuracy(self):
        rows = evaluation.sample([fixture()]); self.assertEqual(len({r['split'] for r in rows}), 1)
        result = evaluation.metrics(rows, {}, {})
        self.assertEqual(result['human_confirmed'], 0)
        self.assertIsNone(result['splits']['holdout']['noise_removal_rate'])

    def test_unknown_and_shortcode_are_not_noise_by_themselves(self):
        item = fixture(); raw = item['blocks'][0]['ocr_original']
        raw['b']['text'] = 'https://gist.github.com'; raw['b']['score'] = .99
        self.assertEqual(reading.selection(item)[1]['state'], 'keep')
        self.assertTrue(reading.selection(item)[1]['uncertain'])

    def test_low_score_not_overridden_by_ai(self):
        item = fixture(); row = reading.rules(item)[2]
        item['reading_selection'] = {'ai': {row['id']: {'category': 'interface', 'source_key': row['source_key']}}}
        self.assertEqual(reading.selection(item)[2]['state'], 'fold')


class ReadingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.patches = [patch.object(store, 'DATA', root), patch.object(store, 'DB', root/'test.sqlite3')]
        for p in self.patches: p.start()
        store.init()
        self.item = {**fixture(), 'status': 'ready', 'note': '', 'note_revision': 0}
        articles.save(self.item)

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_topic_default_hidden_and_stale_projection(self):
        topic = research.attach_material('sample', 'test')['topic_id']
        self.assertEqual(topic_search.search(topic, 'MCP')['items'], [])
        hidden = topic_search.search(topic, 'MCP', include_hidden=True)['items'][0]
        self.assertIn('MCP', topic_search.context(topic, hidden['hit_id'], hidden['source_hash'], True)['text'])
        with self.assertRaises(documents.Conflict): topic_search.context(topic, hidden['hit_id'], hidden['source_hash'])
        row = reading.selection(self.item)[2]
        reading.override('sample', row['id'], row['source_key'], 0, 'body', 'keep')
        self.assertTrue(topic_search.search(topic, 'MCP')['items'])
        with self.assertRaises(documents.Conflict): reading.override('sample', row['id'], row['source_key'], 0, 'body', 'exclude')
        self.assertEqual(articles.get('sample')['blocks'], self.item['blocks'])

    def test_human_labels_do_not_change_selection_or_use_manual_as_model_quality(self):
        rows = evaluation.prepared(); row = rows[0]
        result = evaluation.label('sample', row['id'], row['source_key'], 'body', 0)
        self.assertEqual(result['comparisons']['rules']['human_confirmed'], 1)
        self.assertEqual(articles.get('sample'), self.item)
        with self.assertRaises(documents.Conflict): evaluation.label('sample', row['id'], row['source_key'], 'body', 0)
        original_report = result['comparisons']['ai']
        reading.override('sample', row['id'], row['source_key'], 0, 'interface', 'exclude')
        self.assertEqual(evaluation.report()['comparisons']['ai'], original_report)
