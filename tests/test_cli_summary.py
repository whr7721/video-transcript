import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cli_summary as summary
import documents
import organizer
import store


def bundle():
    return dict(summary=[dict(text='核心观点',source_ids=['seg-0'])],highlights=[dict(text='亮点',source_ids=['seg-0'])],tags=['测试'],questions=['如何验证？'],terms=[],quotes=[dict(text='原始讲话',source_ids=['seg-0'])],root=dict(text='主题',children=[dict(text='要点')]))


class SummaryCLI(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name)
        self.directory=self.root/'jobs'/'1234567890abcdef'
        self.directory.mkdir(parents=True)
        self.result={'text':'原始讲话：核心观点。','segments':[dict(start=1,end=3,text='原始讲话：核心观点。')]}
        for ext,data in [('json',json.dumps(self.result,ensure_ascii=False)),('txt',self.result['text']),('srt','source fixture')]:
            (self.directory/('transcript.'+ext)).write_text(data,encoding='utf8')
        self.before={p.name:p.read_bytes() for p in self.directory.glob('transcript.*')}
        self.p1=patch.object(store,'DATA',self.root);self.p2=patch.object(store,'DB',self.root/'tasks.sqlite3');self.p1.start();self.p2.start()
        self.calls=[]
    def tearDown(self):self.p2.stop();self.p1.stop();self.tmp.cleanup()
    def request(self,system,user,max_tokens):
        self.calls.append(system)
        return (dict(blocks=[dict(kind='paragraph',text='完整整理稿')]) if system==summary.manuscript.ARTICLE_PROMPT else bundle()),dict(total_tokens=10)
    def unchanged(self):self.assertEqual(self.before,{p.name:p.read_bytes() for p in self.directory.glob('transcript.*')})
    def test_two_calls_then_zero_cached_calls_and_offline_export(self):
        summary.summarize(self.directory,self.request);self.assertEqual(len(self.calls),2)
        summary.summarize(self.directory,self.request);self.assertEqual(len(self.calls),2)
        md=(self.directory/'summary.md').read_text(encoding='utf8');self.assertIn('00:00:01–00:00:03',md);self.assertIn('完整整理稿',md)
        html=(self.directory/'mindmap.html').read_text(encoding='utf8');self.assertIn('Markmap.create',html);self.assertNotIn('<script src=',html)
        self.unchanged()
    def test_failed_second_stage_retries_only_second(self):
        def fail(system,user,max_tokens):
            if system==summary.PROMPT:raise RuntimeError('quota fixture')
            return self.request(system,user,max_tokens)
        with self.assertRaisesRegex(RuntimeError,'quota'):summary.summarize(self.directory,fail)
        self.unchanged();self.assertFalse((self.directory/'summary.md').exists())
        summary.summarize(self.directory,self.request);self.assertEqual(len(self.calls),2);self.unchanged()
    def test_export_failure_retries_without_model(self):
        with patch.object(summary,'mindmap_html',side_effect=RuntimeError('assets unavailable')):
            with self.assertRaisesRegex(RuntimeError,'assets'):summary.summarize(self.directory,self.request)
        self.unchanged();summary.summarize(self.directory,self.request);self.assertEqual(len(self.calls),2)
    def test_invalid_quote_is_rejected_and_retry_keeps_article(self):
        def bad(system,user,max_tokens):
            if system!=summary.PROMPT:return self.request(system,user,max_tokens)
            b=bundle();b['quotes'][0]['text']='不存在的原话';return b,dict(total_tokens=12)
        with self.assertRaises(RuntimeError):summary.summarize(self.directory,bad)
        self.unchanged();summary.summarize(self.directory,self.request);self.assertEqual(len(self.calls),2)
    def test_default_request_uses_shared_quota(self):
        with patch.object(summary.settings,'cloud_key',return_value='fixture'),patch.object(organizer,'reserve_daily_call',side_effect=RuntimeError('daily quota')):
            with self.assertRaisesRegex(RuntimeError,'daily quota'):summary.summarize(self.directory)
        self.unchanged()
    def test_untimed_reference_does_not_invent_timestamp(self):
        self.assertEqual(summary.source_label(['seg-0'],[dict(id='seg-0',text='原文')]),'seg-0（无时间轴）')
    def test_cached_cli_transcript_can_trigger_summary_without_download(self):
        import argparse,hashlib,shiwen
        url='https://youtu.be/fixture'
        ident=hashlib.sha256((url+'|auto').encode()).hexdigest()[:16]
        d=self.root/'jobs'/ident;d.mkdir();(d/'transcript.json').write_text(json.dumps(self.result))
        with patch.object(shiwen,'ytdlp',side_effect=AssertionError('no download')),patch.object(summary,'summarize') as call:
            shiwen.add(argparse.Namespace(url=url,episode=None,language='auto',summarize=True));call.assert_called_once_with(d)
    def test_existing_lock_prevents_duplicate_paid_work(self):
        with summary.job_lock(self.directory):
            with self.assertRaises(RuntimeError):summary.summarize(self.directory,self.request)
        self.assertEqual(self.calls,[])
