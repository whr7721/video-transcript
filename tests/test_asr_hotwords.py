"""ASR 专名纠正：归一化匹配、边界安全、原稿保留、词表可维护、接入点生效。"""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import asr_hotwords as hotwords
import link_ingest
import store
import transcript_stage


class CorrectTests(unittest.TestCase):
    def test_case_space_and_punctuation_insensitive(self):
        mapping = {'SnoLuma': ['snow luer', 'snow鲁码']}
        for text in ['打开snowluer看看', '打开 SNOW LUER 看看', '打开 snow-luer 看看', '装一下snow鲁码']:
            with self.subTest(text=text):
                fixed, details = hotwords.correct(text, mapping)
                self.assertIn('SnoLuma', fixed)
                self.assertEqual(sum(item['count'] for item in details), 1)

    def test_longest_variant_wins_and_no_corruption(self):
        mapping = {'harness': ['harnes', 'harnessness'], 'DeepSeek': ['deeps', 'deep sickick']}
        fixed, details = hotwords.correct('在 harnessness 里，也是 harness，还有 deep sickick 和 deeps', mapping)
        self.assertEqual(fixed, '在 harness 里，也是 harness，还有 DeepSeek 和 DeepSeek')
        self.assertNotIn('harnesss', fixed)
        counts = {item['term']: item['count'] for item in details}
        self.assertEqual(counts, {'harness': 1, 'DeepSeek': 2})

    def test_latin_boundaries_do_not_eat_neighbours(self):
        fixed, details = hotwords.correct('harness 和 deepseek 都不是变体', {'harness': ['harnes'], 'DeepSeek': ['deeps']})
        self.assertEqual(fixed, 'harness 和 deepseek 都不是变体')
        self.assertEqual(details, [])

    def test_cjk_adjacent_variant_matches(self):
        fixed, details = hotwords.correct('没有下载honess的，可以在这里下载', {'harness': ['honess']})
        self.assertEqual(fixed, '没有下载harness的，可以在这里下载')
        self.assertEqual(details[0]['variants'], {'honess': 1})

    def test_empty_and_clean_text_is_untouched(self):
        for text in ['', '   ', '全是中文没有专名']:
            fixed, details = hotwords.correct(text, {'harness': ['honess']})
            self.assertEqual(fixed, text)
            self.assertEqual(details, [])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ps = [patch.object(store, 'DATA', self.root), patch.object(store, 'DB', self.root/'tasks.sqlite3')]
        for p in self.ps: p.start()
        store.init()

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def test_apply_keeps_raw_text_corrects_segments_and_is_idempotent(self):
        result = {'text': '先装 deep sickick，再装 honess。', 'review_note': '原文由语音识别生成。',
                  'segments': [{'start': 0, 'end': 1, 'text': '先装 deep sickick'}, {'start': 1, 'end': 2, 'text': '再装 honess。'}]}
        once = hotwords.apply(result)
        self.assertEqual(once['text'], '先装 DeepSeek，再装 harness。')
        self.assertEqual(once['raw_text'], '先装 deep sickick，再装 honess。')
        self.assertEqual([s['text'] for s in once['segments']], ['先装 DeepSeek', '再装 harness。'])
        self.assertEqual(sum(item['count'] for item in once['corrections']), 2)
        self.assertIn('已按专名表纠正 2 处英文专名', once['review_note'])
        twice = hotwords.apply(once)
        self.assertIs(twice, once)
        self.assertEqual(twice['text'], once['text'])

    def test_no_hit_adds_empty_corrections_without_raw_text(self):
        result = {'text': '全是中文', 'segments': []}
        applied = hotwords.apply(result)
        self.assertEqual(applied['corrections'], [])
        self.assertNotIn('raw_text', applied)
        self.assertEqual(applied['text'], '全是中文')

    def test_user_table_extends_defaults(self):
        (self.root/'hotwords.json').write_text(json.dumps({'Qwen': ['quen model'], 'DeepSeek': ['deep sickick']}), encoding='utf-8')
        table = hotwords.table()
        self.assertIn('Qwen', table)
        self.assertIn('deep sickick', table['DeepSeek'])
        self.assertIn('harness', table)
        fixed, _ = hotwords.correct('用 quen model 和 deep sickick', table)
        self.assertEqual(fixed, '用 Qwen 和 DeepSeek')

    def test_missing_table_file_is_created_for_editing(self):
        hotwords.apply({'text': '全是中文', 'segments': []})
        path = self.root/'hotwords.json'
        self.assertTrue(path.is_file())
        self.assertIn('DeepSeek', json.loads(path.read_text(encoding='utf-8')))


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ps = [patch.object(store, 'DATA', self.root), patch.object(store, 'DB', self.root/'tasks.sqlite3')]
        for p in self.ps: p.start()
        store.init()

    def tearDown(self):
        for p in reversed(self.ps): p.stop()
        self.tmp.cleanup()

    def test_link_export_writes_corrected_text_and_keeps_raw(self):
        directory = self.root/'jobs'/('a'*16); directory.mkdir(parents=True)
        result = {'text': '先装 deep sickick', 'segments': [{'start': 0, 'end': 1, 'text': '先装 deep sickick'}]}
        exported = link_ingest.export(directory, result, {'title': '样例'})
        stored = json.loads((directory/'transcript.json').read_text(encoding='utf-8'))
        self.assertEqual(stored['text'], '先装 DeepSeek')
        self.assertEqual(stored['raw_text'], '先装 deep sickick')
        self.assertEqual(exported['subtitlesArray'][0]['text'], '先装 DeepSeek')
        self.assertEqual((directory/'transcript.txt').read_text(encoding='utf-8'), '先装 DeepSeek')

    def test_finish_transcription_corrects_json_txt_and_markdown(self):
        directory = self.root/'jobs'/('b'*16); directory.mkdir(parents=True)
        updates = []
        noisy = {'text': '没有下载honess的', 'segments': [{'start': 0, 'end': 1, 'text': '没有下载honess的'}]}
        with patch('transcribe.local_transcribe', return_value=noisy), patch('media_buffer.state'):
            transcript_stage.finish_transcription({'id': 'b'*16, 'provider': 'local', 'language': 'zh'},
                                                  lambda **fields: updates.append(fields), directory,
                                                  directory/'audio.wav', 1, {'title': '样例', 'source_url': 'https://example.org/v'}, time.perf_counter(), False)
        stored = json.loads((directory/'transcript.json').read_text(encoding='utf-8'))
        self.assertEqual(stored['text'], '没有下载harness的')
        self.assertEqual(stored['raw_text'], '没有下载honess的')
        self.assertIn('纠正 1 处英文专名', stored['review_note'])
        self.assertIn('没有下载harness的', (directory/'transcript.md').read_text(encoding='utf-8'))
        self.assertEqual(updates[-1]['result']['text'], '没有下载harness的')


if __name__ == '__main__':
    unittest.main()
