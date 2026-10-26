import copy
import unittest
from unittest.mock import patch
import image_editorial as editorial
import articles
import ocr_reading
import tests.test_ocr_reading as fixtures


class EditorialTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReadingIntegrationTests.setUp(self)
        self.item['editorial']={'status':'queued'}
        articles.save(self.item)

    def tearDown(self):
        fixtures.ReadingIntegrationTests.tearDown(self)

    def test_full_input_includes_folded_and_excluded_regions(self):
        pages,raw,_=editorial.source(self.item)
        self.assertEqual(len(pages),1)
        self.assertIn('MCP',raw);self.assertIn('12:33',raw)
        self.assertIn('原始OCR错宇',raw)

    def test_full_article_and_essence_preserve_original_and_notes(self):
        before=copy.deepcopy(self.item)
        article={'blocks':[{'kind':'heading','text':'完整稿'},{'kind':'paragraph','text':'根据材料整理的自然段'}]}
        essence={'blocks':[{'kind':'paragraph','text':'简短精华'}]}
        with patch.object(editorial,'request',side_effect=[(article,{}),(essence,{})]):
            editorial.run('sample')
        item=articles.get('sample')
        self.assertEqual(item['blocks'],before['blocks']);self.assertEqual(item['note'],before['note'])
        self.assertEqual(item['editorial']['status'],'completed')
        self.assertIn('完整稿',editorial.export('sample'))
        with patch.object(editorial.settings,'cloud_key',return_value='test'),patch.object(articles.TEXT_EXECUTOR,'submit') as submit:
            editorial.start('sample');self.assertFalse(submit.called)

    def test_essence_failure_keeps_readable_full_article_and_retries_only_essence(self):
        value={'blocks':[{'kind':'paragraph','text':'完整的正文'}]}
        with patch.object(editorial,'request',side_effect=[(value,{}),RuntimeError('timeout')]):editorial.run('sample')
        self.assertEqual(articles.get('sample')['editorial']['status'],'completed')
        self.assertIn('timeout',articles.get('sample')['editorial']['essence_error'])
        with patch.object(editorial,'request',return_value=(value,{})) as call:editorial.run('sample');self.assertEqual(call.call_count,1)

    def test_full_failure_keeps_previous_content_and_source_change_marks_stale(self):
        self.item['editorial']={'status':'queued','content':{'type':'doc','content':[]},'source_hash':'old'};articles.save(self.item)
        with patch.object(editorial,'request',side_effect=RuntimeError('timeout')):editorial.run('sample')
        item=articles.get('sample');self.assertEqual(item['editorial']['status'],'failed')
        self.assertTrue(ocr_reading.view(item)['editorial']['stale'])
