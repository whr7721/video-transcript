import io,json,tempfile,unittest,zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import collection_summary as cs,diarization,link_ingest,library,store,xmind_export
class ZeroGap(unittest.TestCase):
 def test_xmind_tree_is_same_validated_unicode_tree(self):
  tree={'text':'主题','children':[{'text':'分支'}]}
  with zipfile.ZipFile(io.BytesIO(xmind_export.export(tree))) as z:
   sheet=json.loads(z.read('content.json'))[0];self.assertEqual(sheet['rootTopic']['title'],'主题');self.assertEqual(sheet['rootTopic']['children']['attached'][0]['title'],'分支');self.assertIn('metadata.json',z.namelist())
 def test_speaker_overlap_preserves_text_and_srt(self):
  value={'text':'原文','segments':[{'start':0,'end':2,'text':'原文'}]};out=diarization.annotate(value,[{'start':0,'end':1.8,'speaker':'说话人1'}])
  self.assertEqual(value['segments'][0].get('speaker'),None);self.assertEqual(out['text'],value['text'])
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
   link_ingest.export(Path(tmp),out,{})
   self.assertIn('[说话人1]',(Path(tmp)/'transcript.srt').read_text(encoding='utf8'))
 def test_diarization_identity_does_not_overwrite_plain_transcript(self):
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp:
   f=SimpleNamespace(name=str(Path(tmp)/'sample.wav'));Path(f.name).write_bytes(b'audio fixture')
   plain=link_ingest.prepare(SimpleNamespace(url=f.name,language='auto'))
   speaker=link_ingest.prepare(SimpleNamespace(url=f.name,language='auto',diarize=True,speakers=2))
   self.assertNotEqual(plain['ident'],speaker['ident'])
 def test_aggregate_cache_invalidation_failure_keeps_saved_summary(self):
  rows=[{'id':'audio:1','title':'甲','text':'事实'}];calls=[]
  def request(*a,**kw):calls.append(1);return {'summary':'事实[audio:1]'},{'total_tokens':1}
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp,patch.object(store,'DATA',Path(tmp)),patch.object(cs,'snapshot',side_effect=lambda _:rows):
   first=cs.generate('a',request);self.assertTrue(cs.generate('a',request)['cached']);self.assertEqual(len(calls),1)
   rows[0]['text']='事实变化';self.assertTrue(cs.state('a')['stale'])
   with self.assertRaises(ValueError):cs.generate('a',lambda *a,**kw:({'summary':'没有引用'},{}))
   self.assertEqual(cs.saved('a')['summary'],first['summary'])
 def test_large_aggregate_maps_all_source_parts(self):
  rows=[{'id':'audio:1','title':'长文','text':'前'*7000+'尾'*7000}];seen=[]
  def request(system,user,**kw):seen.append(user);return {'summary':'归纳[audio:1]'},{}
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp,patch.object(store,'DATA',Path(tmp)),patch.object(cs,'snapshot',return_value=rows):cs.generate('b',request)
  self.assertGreater(len(seen),1);self.assertTrue(any('尾' in s for s in seen))
 def test_channel_filter(self):
  record={'uid':'audio:1','id':'1','title':'甲','platform':'youtube','channelId':'channel-a','channelTitle':'频道甲','created_at':0,'duration':0,'blocks':[]}
  with tempfile.TemporaryDirectory(dir=store.ROOT/'runtime') as tmp,patch.object(store,'DATA',Path(tmp)),patch.object(store,'DB',Path(tmp)/'tasks.sqlite3'),patch.object(library,'sync',return_value=[record]):
   with store.connect() as db:library.init(db)
   self.assertEqual(len(library.listing(q='',channel_id='channel-a')['items']),1);self.assertEqual(library.listing(q='',channel_id='other')['items'],[])
if __name__=='__main__':unittest.main()
