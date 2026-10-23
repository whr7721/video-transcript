import copy
import unittest
import chapters


class ChapterRangeTests(unittest.TestCase):
    def task(self):
        return {'id': 'sample', 'result': {'segments': [
            {'text': '重复句。' * 3000}, {'text': '   '},
            {'text': '重复句。尾声', 'start': 90, 'end': 92}]}}

    def test_lossless_long_and_repeated(self):
        task = self.task()
        original = copy.deepcopy(task)
        view = chapters.snapshot(task)
        plan = chapters.reading_sections(view)
        self.assertTrue(chapters.validate(view, plan))
        text = ''.join(chapters.resolve(view, plan, i)['text'] for i in range(len(plan['sections'])))
        self.assertEqual(text, ''.join(s['text'] for s in view['sources']))
        self.assertEqual(task, original)
        self.assertNotIn('start', chapters.resolve(view, plan, 0)['ranges'][0])
        self.assertEqual(plan, chapters.reading_sections(chapters.snapshot(task)))

    def test_reject_missing_duplicate_reordered_and_stale(self):
        view = chapters.snapshot(self.task())
        for mode in ('missing', 'duplicate', 'reverse', 'stale'):
            plan = chapters.reading_sections(view)
            ids = plan['sections'][0]['fragment_ids']
            if mode == 'missing': ids.pop()
            if mode == 'duplicate': ids.append(ids[0])
            if mode == 'reverse': ids.reverse()
            if mode == 'stale': plan['source_hash'] = 'old'
            with self.assertRaises(ValueError): chapters.validate(view, plan)

    def test_empty_and_small_target(self):
        view = chapters.snapshot({'id': 'empty', 'result': {'text': ''}})
        self.assertTrue(chapters.validate(view, chapters.reading_sections(view)))
        view = chapters.snapshot({'id': 'small', 'result': {'text': '小段'}})
        self.assertTrue(chapters.validate(view, chapters.reading_sections(view, 1)))
        with self.assertRaises(ValueError): chapters.reading_sections(view, 0)

class ChapterStorageTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import store
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(store, 'DB', Path(self.temp.name)/'test.sqlite')
        self.data_patch = patch.object(store, 'DATA', Path(self.temp.name))
        self.patch.start(); self.data_patch.start()
        self.task = {'id':'aaaaaaaaaaaaaaaa','status':'completed','duration':120,
                     'result':{'segments':[{'text':'重复句。','start':0,'end':40},
                                           {'text':'重复句。后半段','start':60,'end':120}]}}

    def tearDown(self):
        self.patch.stop(); self.data_patch.stop(); self.temp.cleanup()

    def test_version_conflict_and_stale_snapshot(self):
        plan = chapters.get(self.task)
        saved = chapters.save(self.task, plan, 0)
        self.assertEqual(saved['revision'],1)
        self.assertEqual(chapters.get(self.task),saved)
        with self.assertRaises(chapters.Conflict):chapters.save(self.task,plan,0)
        self.task['result']['segments'][0]['text'] += '变更'
        self.assertTrue(chapters.get(self.task)['stale'])
        with self.assertRaises(ValueError):chapters.resolve(chapters.snapshot(self.task),saved,0)

    def test_official_mapping_hidden_and_gap(self):
        import json
        view = chapters.snapshot(self.task)
        data = json.dumps({'version':'1.2','chapters':[{'startTime':10,'title':'主题'},
                           {'startTime':30,'toc':False},{'startTime':55,'title':'结尾'}]}).encode()
        plan = chapters.official_plan(view,data,120)
        self.assertTrue(chapters.validate(view,plan))
        self.assertEqual(''.join(chapters.resolve(view,plan,i)['text'] for i in range(len(plan['sections']))),'重复句。重复句。后半段')
        self.assertEqual(len(plan['official_markers']),3)
        saved = chapters.save(self.task,plan,0)
        self.assertEqual(saved['origin'],'official')
        self.assertEqual(len(chapters.get(self.task)['official_markers']),3)

    def test_official_rejects_invalid_times_and_untimed(self):
        import json
        view = chapters.snapshot(self.task)
        for rows in ([{'startTime':-1}],[{'startTime':120}],[{'startTime':20},{'startTime':10}],
                     [{'startTime':True}],[{'startTime':float('nan')}],[{'startTime':0,'endTime':140}]):
            with self.assertRaises(ValueError):
                chapters.official_plan(view,json.dumps({'version':'1.2','chapters':rows}).encode(),120)
        view = chapters.snapshot({'id':'plain','result':{'text':'纯文本'}})
        with self.assertRaises(ValueError):chapters.official_plan(view,b'{"version":"1.2","chapters":[{"startTime":0}]}',120)

    def test_http_save_and_exact_second_occurrence(self):
        import store
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from studio_api import router
        store.init();store.save(self.task)
        app = FastAPI();app.include_router(router)
        client = TestClient(app)
        base = '/api/studio/documents/'+self.task['id']
        plan = client.get(base+'/chapters').json()
        plan['sections'] = [{'title':'前半','fragment_ids':['seg-0:0:4']},
                            {'title':'后半','fragment_ids':['seg-1:0:7']}]
        # Use actual offsets rather than depending on glyph counts in fixture.
        parts=chapters.fragments(chapters.snapshot(self.task))
        for section,part in zip(plan['sections'],parts):section['fragment_ids']=[part['id']]
        response=client.post(base+'/chapters',json={'revision':0,'plan':plan})
        self.assertEqual(response.status_code,200,response.text)
        exact=client.get(base+'/chapters/1/text').json()
        self.assertEqual(exact['ranges'][0]['source_id'],'seg-1')
        self.assertEqual(exact['text'],'重复句。后半段')
        self.assertEqual(client.post(base+'/chapters',json={'revision':0,'plan':plan}).status_code,409)
        self.assertEqual(client.post(base+'/official-chapters',json={'revision':1,'plan':{}}).status_code,400)

    def test_official_http_only_fetches_saved_url(self):
        import store
        from unittest.mock import patch
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from studio_api import router
        store.init()
        self.task['source']={'kind':'podcast','chapters_url':'https://example.org/chapters.json'}
        store.save(self.task)
        app=FastAPI();app.include_router(router);client=TestClient(app)
        url='/api/studio/documents/'+self.task['id']+'/official-chapters'
        data=b'{"version":"1.2","chapters":[{"startTime":0,"title":"opening"},{"startTime":50,"title":"end"}]}'
        with patch('article_fetch.fetch',return_value=(data,'application/json+chapters','https://example.org/chapters.json')) as fetch:
            result=client.post(url,json={'revision':0,'plan':{'url':'http://127.0.0.1/evil'}})
            self.assertEqual(result.status_code,200,result.text)
            fetch.assert_called_once_with('https://example.org/chapters.json',limit=1_000_000)
        self.assertEqual(result.json()['origin'],'official')

    def test_feed_chapter_url_is_metadata_only(self):
        import podcast_feed
        data=b'''<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0"><channel><title>Sample</title><item><title>Episode</title><guid>sample</guid><podcast:chapters url="https://example.org/c.json" type="application/json+chapters"/><enclosure url="https://example.org/a.mp3" type="audio/mpeg" length="10"/></item></channel></rss>'''
        feed=podcast_feed.parse(data,'https://example.org/rss')
        self.assertEqual(feed['episodes'][0]['chapters_url'],'https://example.org/c.json')
