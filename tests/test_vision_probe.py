import copy
import json
import unittest
from unittest.mock import Mock, patch
import articles
import ocr_classification as costs
import store
from experiments.vision import client as vision
from tests import test_ocr_reading as fixtures


class VisionTests(unittest.TestCase):
    def setUp(self):
        fixtures.ReadingIntegrationTests.setUp(self)
        self.directory=store.DATA/'articles'/'sample'
        self.directory.mkdir(parents=True,exist_ok=True)
        self.image=self.item['blocks'][0]
        self.image.update(asset_status='saved',asset_name='test.png')
        (self.directory/'test.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')

    def tearDown(self):fixtures.ReadingIntegrationTests.tearDown(self)

    def test_original_images_not_ocr_are_sent_and_input_is_unchanged(self):
        before=copy.deepcopy(self.item)
        payload=vision.payload(self.item)
        self.assertEqual(self.item,before)
        self.assertIn('data:image/png;base64,',payload[-1]['image_url']['url'])
        self.assertNotIn('原始OCR错宇',json.dumps(payload,ensure_ascii=False))
        key=vision.source(self.item)[2]
        self.image['asset_name']='replacement.png'
        self.assertNotEqual(key,vision.source(self.item)[2])

    def test_missing_page_and_outside_asset_are_rejected_without_request(self):
        for value in ['../outside.png','..\\outside.png','missing.png']:
            self.image['asset_name']=value
            with self.assertRaises(ValueError):vision.payload(self.item)
        self.image['asset_status']='missing'
        with self.assertRaises(ValueError):vision.source(self.item)

    def response(self,finish='stop',content='{"blocks":[]}'):
        data={'choices':[{'finish_reason':finish,'delta':{'content':content}}],
              'usage':{'prompt_tokens':150000,'completion_tokens':1000}}
        return Mock(status_code=200,headers={},iter_lines=lambda:iter(['data: '+json.dumps(data),'data: [DONE]']))

    def test_truncated_response_is_metered_but_never_accepted(self):
        with patch.object(vision.httpx,'Client') as client,patch.object(vision.settings,'cloud_key',return_value='test'):
            client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value=self.response('length')
            with self.assertRaisesRegex(RuntimeError,'截断'):vision.request('test',[],1000)
        with store.connect() as db:
            row=db.execute('SELECT estimated,status FROM ocr_filter_calls').fetchone()
            self.assertAlmostEqual(row[0],.2528);self.assertEqual(row[1],'failed')
        self.assertEqual(len(list((store.DATA/'vision-reading-candidates').glob('*-failed.json'))),1)

    def test_budget_is_shared_with_ocr_and_text(self):
        costs.reserve(9.3)
        with patch.object(vision.httpx,'Client') as client:
            with self.assertRaisesRegex(RuntimeError,'预算'):vision.request('test',[],32768)
            client.assert_not_called()

    def test_success_and_json_error_both_use_actual_model_rates(self):
        with patch.object(vision.httpx,'Client') as client,patch.object(vision.settings,'cloud_key',return_value='test'):
            response=client.return_value.__enter__.return_value.stream.return_value.__enter__
            response.return_value=self.response()
            _,usage=vision.request('test','text',1000)
            self.assertEqual(usage['estimated_cny'],.2528)
            response.return_value=self.response(content='broken')
            with self.assertRaises(ValueError):vision.request('test','text',1000)
        with store.connect() as db:
            self.assertEqual([r[0] for r in db.execute('SELECT status FROM ocr_filter_calls ORDER BY id')],['completed','failed'])

    def test_failed_second_section_resumes_from_first_without_rebilling_it(self):
        item=copy.deepcopy(self.item)
        item['blocks']=[{**self.image,'id':f'image-{i+1}','page':i+1} for i in range(7)]
        first={'blocks':[{'kind':'paragraph','text':'前段正文'}],'essence_blocks':[{'kind':'paragraph','text':'前段精华'}]}
        second={'blocks':[{'kind':'paragraph','text':'后段正文'}],'essence_blocks':[{'kind':'paragraph','text':'后段精华'}]}
        with patch.object(vision,'payload',return_value=[]),patch.object(vision,'request',side_effect=[(first,{'total_tokens':10}),RuntimeError('timeout')]):
            with self.assertRaisesRegex(RuntimeError,'timeout'):vision.read(item)
        with patch.object(vision,'payload',return_value=[]),patch.object(vision,'request',return_value=(second,{'total_tokens':20})) as call:
            value,usage=vision.read(item)
            self.assertEqual(call.call_count,1)
            self.assertEqual([b['text'] for b in value['blocks']],['前段正文','后段正文'])
            self.assertEqual([u['total_tokens'] for u in usage],[10,20])

    def test_stream_without_done_is_not_published_even_with_valid_json(self):
        response=self.response()
        response.iter_lines=lambda:iter(['data: '+json.dumps({'choices':[{'finish_reason':'stop','delta':{'content':'{}'}}]})])
        with patch.object(vision.httpx,'Client') as client,patch.object(vision.settings,'cloud_key',return_value='test'):
            client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value=response
            with self.assertRaisesRegex(RuntimeError,'未完整结束'):vision.request('test','text',1000)

if __name__=='__main__':unittest.main()
