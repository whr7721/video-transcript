import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
import app
import articles
import article_fetch
import article_parser
import documents
import organizer
import store


HTML='''<html><title>工具指南</title><body><article><h2>安装</h2><p>先准备模型文件，再执行下面的命令。</p><pre><code>pip install demo\n  --path D:/models</code></pre><p>效果<img data-src="https://example.com/one.png" alt="效果图">结论</p><table><tr><td>步数</td><td>8</td></tr></table><a href="https://example.com/docs">官方说明</a><script>alert(1)</script></article></body></html>'''

class ArticleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'test.sqlite3')]
        for p in self.patches:p.start()
        store.init()

    def tearDown(self):
        for p in self.patches:p.stop()
        self.tmp.cleanup()

    def item(self):
        with patch.object(articles.EXECUTOR,'submit'):item=articles.start('html',HTML)
        with patch.object(article_fetch,'fetch',return_value=(b'\x89PNG\r\n\x1a\nmock','image/png','https://example.com/one.png')):
            articles.run(item,HTML)
        return item

    def test_code_image_table_order_and_no_script(self):
        value=article_parser.parse(HTML)
        self.assertEqual([b['type'] for b in value['blocks']],['heading','paragraph','code','paragraph','image','paragraph','table','link'])
        self.assertEqual(value['blocks'][2]['text'],'pip install demo\n  --path D:/models')
        self.assertEqual(value['blocks'][4]['url'],'https://example.com/one.png')
        self.assertNotIn('alert(1)',json.dumps(value))
        self.assertEqual(value['completeness'],'unverified')

    def test_challenge_and_wechat_missing_body_are_rejected(self):
        for html,url in [('<p>环境异常，请完成验证</p>','https://mp.weixin.qq.com/s/abc'),('<p>正常但无正文</p>','https://mp.weixin.qq.com/s/abc')]:
            with self.assertRaises(ValueError):article_parser.parse(html,source_url=url)

    def test_manual_paste_flags_missing_images_and_preserves_words(self):
        value=article_parser.parse('原话不能改。\n\n图片\n\n数字123。','text')
        self.assertEqual(value['blocks'][0]['text'],'原话不能改。');self.assertEqual(value['completeness'],'partial')
        self.assertTrue(any('原图' in w for w in value['warnings']))

    def test_image_placeholder_with_caption_and_nested_html_text_are_not_lost(self):
        value=article_parser.parse('前文。\n\n图片\n原图图注。\n\n后文。','text')
        self.assertEqual(value['completeness'],'partial');self.assertIn('原图图注。',[b['text'] for b in value['blocks']])
        html='<article><p><span>前文<img src="https://example.com/a.png">后文<br>换行</span></p></article>'
        value=article_parser.parse(html)
        self.assertEqual([b['text'] for b in value['blocks']],['前文','','后文\n换行'])

    def test_dedup_and_different_source_remain_distinct(self):
        with patch.object(articles.EXECUTOR,'submit') as submit:
            a=articles.start('text','同一份原文');b=articles.start('text','同一份原文');c=articles.start('text','同一份原文',source_url='https://example.com/other')
        self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['id'],c['id']);self.assertEqual(submit.call_count,2)

    def test_missing_image_is_not_complete(self):
        with patch.object(articles.EXECUTOR,'submit'):item=articles.start('html',HTML)
        with patch.object(article_fetch,'fetch',side_effect=ValueError('failed')):articles.run(item,HTML)
        self.assertEqual(item['status'],'ready');self.assertEqual(item['completeness'],'partial')
        self.assertEqual(next(b for b in item['blocks'] if b['type']=='image')['asset_status'],'missing')

    def test_note_conflict_and_source_immutable(self):
        item=self.item();before=copy.deepcopy(item['blocks'])
        changed=articles.note(item['id'],0,'我的笔记')
        self.assertEqual(changed['blocks'],before)
        with self.assertRaises(documents.Conflict):articles.note(item['id'],0,'旧输入')
        self.assertEqual(articles.get(item['id'])['note'],'我的笔记')

    def test_inflight_import_cannot_overwrite_note(self):
        with patch.object(articles.EXECUTOR,'submit'):item=articles.start('text','原文')
        with self.assertRaises(ValueError):articles.note(item['id'],0,'不要丢失')

    def test_model_answer_filters_forged_quotes_and_preserves_notes(self):
        item=self.item();articles.note(item['id'],0,'已经写好的笔记');before=copy.deepcopy(item['blocks'])
        response={'sections':[{'heading':'准备','text':'先准备文件。','block_id':'b2','quote':'先准备模型文件'},
                             {'heading':'编造','text':'假的','block_id':'b2','quote':'这里没有这句话'}],'gaps':['原文未提供你的显卡性能。']}
        with patch.object(organizer,'request_json',return_value=(response,{})):articles.answer(item['id'],'怎么操作？')
        after=articles.get(item['id']);self.assertEqual(after['blocks'],before);self.assertEqual(after['note'],'已经写好的笔记')
        self.assertEqual(len(after['artifacts']),1);self.assertEqual(after['artifacts'][0]['rejected'],1)
        self.assertIn('原文 [b2]',articles.export(item['id']))

    def test_model_failure_does_not_destroy_previous_results(self):
        item=self.item()
        with patch.object(organizer,'request_json',side_effect=RuntimeError('已达上限')):articles.answer(item['id'],'怎么操作？')
        self.assertEqual(articles.get(item['id'])['question_status'],'failed')
        self.assertEqual(articles.get(item['id'])['blocks'],item['blocks'])

    def test_api_origin_revision_and_asset_allowlist(self):
        item=self.item()
        with TestClient(app.app) as client:
            url='/api/library/items/'+item['id']
            self.assertEqual(client.put(url+'/note',json={'revision':0,'text':'改'},headers={'Origin':'https://evil.test'}).status_code,403)
            self.assertEqual(client.put(url+'/note',json={'revision':0,'text':'保存'}).status_code,200)
            self.assertEqual(client.put(url+'/note',json={'revision':0,'text':'旧'}).status_code,409)
            self.assertEqual(client.get(url+'/assets/other.png').status_code,404)
            name=next(b['asset_name'] for b in item['blocks'] if b['type']=='image')
            self.assertEqual(client.get(url+'/assets/'+name).status_code,200)

    def test_url_policy_and_dns_private_redirect_protection(self):
        for u in ['http://localhost/','http://127.0.0.1/','http://10.1.2.3/','http://169.254.169.254/','https://name:secret@example.com/','file:///tmp/a','http://example.com:8765/']:
            with self.assertRaises(ValueError):article_fetch.public_url(u)
        transport=article_fetch.PublicTransport()
        with patch.object(article_fetch.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]),patch.object(httpx.HTTPTransport,'handle_request') as send:
            with self.assertRaises(ValueError):transport.handle_request(httpx.Request('GET','https://public.example.com/'))
            send.assert_not_called()

    def test_public_connection_is_pinned_and_tls_keeps_original_name(self):
        transport=article_fetch.PublicTransport()
        with patch.object(article_fetch.socket,'getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]),patch.object(httpx.HTTPTransport,'handle_request',return_value=httpx.Response(200)) as send:
            transport.handle_request(httpx.Request('GET','https://example.com/doc'))
            request=send.call_args.args[0]
            self.assertEqual(request.url.host,'8.8.8.8');self.assertEqual(request.headers['host'],'example.com');self.assertEqual(request.extensions['sni_hostname'],'example.com')

    def test_recovery_does_not_requeue_lost_payload_or_duplicate_model_cost(self):
        with patch.object(articles.EXECUTOR,'submit'):item=articles.start('text','未完成的原文')
        articles.recover();self.assertEqual(articles.get(item['id'])['status'],'failed')
