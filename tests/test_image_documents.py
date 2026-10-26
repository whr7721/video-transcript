import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import articles
import documents
import image_documents as images
import organizer
import private_images
import research
import store
import topic_search

PNG=b'\x89PNG\r\n\x1a\nfixture'


class ImageDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name)
        self.patches=[patch.object(store,'DATA',root),patch.object(store,'DB',root/'test.sqlite3')]
        for p in self.patches:p.start()
        store.init()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def item(self,count=2):
        item=images.create('面试图集',count)
        for i in range(count):images.put_image(item['id'],i,PNG+str(i).encode())
        return articles.get(item['id'])

    def page(self,index=1,text='Agent上下文管理与缓存'):
        return {'id':'image-'+str(index),'status':'ok','width':100,'height':200,'version':'fixture-v1','seconds':1,
                'regions':[{'id':'r1','text':text,'score':.82,'bbox':[1,2,90,30]}]}

    def complete(self,item):
        images.commit_pages(item['id'],{'pages':[self.page(i+1) for i in range(item['expected_images'])]},final=True)
        return articles.get(item['id'])

    def test_order_missing_pages_and_original_bytes(self):
        item=self.item(45)
        images.commit_pages(item['id'],{'pages':[self.page()]},final=True)
        value=articles.get(item['id'])
        self.assertEqual(len([b for b in value['blocks'] if b['type']=='image']),45)
        self.assertEqual(value['image_status'],'partial');self.assertEqual(value['completeness'],'partial')
        self.assertTrue(any('44/45' in w for w in value['warnings']))
        image=value['blocks'][0];self.assertEqual((store.DATA/'articles'/item['id']/image['asset_name']).read_bytes(),PNG+b'0')

    def test_region_revision_and_rerun_keep_notes_corrections_and_machine_original(self):
        item=self.complete(self.item(1));original=copy.deepcopy(item['blocks'][0]['ocr_original'])
        articles.note(item['id'],0,'我的面试项目实例')
        images.correct(item['id'],'image-1-r1',1,'我校对的Agent上下文')
        with self.assertRaises(documents.Conflict):images.correct(item['id'],'image-1-r1',1,'旧输入')
        images.commit_pages(item['id'],{'pages':[self.page()]},final=True)
        now=articles.get(item['id']);self.assertEqual(now['note'],'我的面试项目实例')
        self.assertEqual(now['blocks'][0]['ocr_original'],original);self.assertEqual(now['blocks'][1]['text'],'我校对的Agent上下文')
        changed=self.page();changed['version']='new-model'
        with self.assertRaises(ValueError):images.commit_pages(item['id'],{'pages':[changed]},final=True)
        self.assertEqual(articles.get(item['id'])['blocks'][1]['text'],'我校对的Agent上下文')

    def test_upload_limits_duplicate_bytes_and_no_silent_eviction(self):
        item=self.item(1)
        with patch.object(articles,'ASSET_CAPACITY',len(PNG)+1):
            images.put_image(item['id'],0,PNG+b'0')
            with self.assertRaises(ValueError):images.put_image(item['id'],0,PNG+b'new')
        for data in [b'not image',b'a'*(images.MAX_IMAGE_BYTES+1)]:
            with self.assertRaises(ValueError):images.put_image(item['id'],0,data)
        with self.assertRaises(ValueError):images.create('too many',65)
        self.assertEqual(articles.get(item['id'])['blocks'][0]['asset_status'],'saved')

    def test_image_source_scope_not_caption_and_question_quote_location(self):
        item=self.complete(self.item(2))
        item['blocks'].insert(0,{'id':'caption','type':'paragraph','text':'作品文案不充当图片识别稿'});articles.save(item)
        self.assertEqual(len(articles.question_blocks(item,2)),1)
        self.assertEqual(articles.question_blocks(item,2)[0]['source_image_id'],'image-2')
        with self.assertRaises(ValueError):articles.question_blocks(item,3)
        response={'sections':[{'heading':'重点','text':'识别稿谈到缓存','block_id':'image-2','quote':'上下文管理与缓存'}]}
        with patch.object(organizer,'request_json',return_value=(response,{})) as call:articles.answer(item['id'],'这一页的要点',2)
        sent=json.loads(call.call_args.args[1]);self.assertEqual([s['id'] for s in sent['blocks']],['image-2'])
        current=articles.get(item['id']);self.assertEqual(current['artifacts'][0]['image_page'],2)
        self.assertIn('识别稿摘录',articles.export(item['id']))

    def test_explicit_topic_membership_and_stale_image_reference(self):
        item=self.complete(self.item(1))
        topic=research.attach_material(item['id'],'Agent学习')['topic_id']
        research.attach_material(item['id'],'Agent学习')
        self.assertEqual(research.topics()[0]['materials_count'],1)
        before=copy.deepcopy(articles.get(item['id']))
        result=topic_search.search(topic,'上下文','original');hit=result['items'][0]
        self.assertEqual(hit['article_id'],item['id'])
        context=topic_search.context(topic,hit['hit_id'],hit['source_hash'])
        self.assertEqual(context['blocks'][0]['source_image_id'],'image-1')
        self.assertEqual(articles.get(item['id']),before)
        images.correct(item['id'],'image-1-r1',1,'新内容')
        with self.assertRaises(documents.Conflict):topic_search.context(topic,hit['hit_id'],hit['source_hash'])

    def test_api_upload_region_edit_source_and_no_key_requirement(self):
        client=TestClient(app.app)
        item=client.post('/api/library/image-items',json={'title':'截图','count':1}).json();ident=item['id']
        self.assertEqual(client.put('/api/library/image-items/'+ident+'/0',content=PNG).status_code,200)
        self.complete(articles.get(ident))
        url='/api/library/image-items/'+ident+'/regions/image-1-r1'
        self.assertEqual(client.put(url,json={'revision':1,'text':'校对内容'}).status_code,200)
        self.assertEqual(client.put(url,json={'revision':1,'text':'过期内容'}).status_code,409)
        self.assertEqual(client.post('/api/studio/research/materials',json={'item_id':ident,'topic_title':'测试专题'}).status_code,200)
        self.assertEqual(client.put('/api/library/image-items/'+ident+'/0',content=PNG,headers={'Origin':'https://evil.example'}).status_code,403)

    def test_private_metadata_adapter_uses_existing_cache_and_validates_input(self):
        self.assertEqual(private_images.resolve('https://www.douyin.com/note/7683044048454544229'),'7683044048454544229')
        for text in ['https://evil.example/note/7683044048454544229','http://127.0.0.1/']:
            with self.assertRaises(ValueError):private_images.resolve(text)
        directory=store.DATA/'image-sources'/'7683044048454544229';directory.mkdir(parents=True)
        value={'id':'7683044048454544229','status':'ok','total':1,'images':[{'urls':['https://example.com/a.jpg']} ]}
        (directory/'source.json').write_text(json.dumps(value))
        with patch.object(private_images,'prepare_session') as session:
            self.assertEqual(private_images.metadata(value['id']),value);session.assert_not_called()

    def test_recovery_and_failure_never_requeue_model_or_delete_original(self):
        item=self.item(1);articles.recover();current=articles.get(item['id'])
        self.assertEqual(current['image_status'],'failed');self.assertEqual(current['blocks'][0]['asset_status'],'saved')
        with patch.object(images,'worker_python',side_effect=ValueError('未安装OCR')):images.run_ocr(item['id'])
        self.assertEqual(articles.get(item['id'])['image_status'],'failed')
        self.assertIn('未安装OCR',articles.get(item['id'])['error'])

    def test_cache_timing_is_not_content_revision_and_upload_can_stop_without_delete(self):
        item=self.complete(self.item(1));before=item['content_hash']
        page=self.page();page['seconds']=999
        images.commit_pages(item['id'],{'pages':[page]},final=True)
        self.assertEqual(articles.get(item['id'])['content_hash'],before)
        incomplete=self.item(1);client=TestClient(app.app)
        response=client.post('/api/library/image-items/'+incomplete['id']+'/stop-upload')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['blocks'][0]['asset_status'],'saved')
        self.assertEqual(response.json()['image_status'],'failed')
