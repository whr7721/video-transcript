import copy,io,json,tempfile,time,unittest,contextlib
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import rewrite as r,store,organizer,shiwen,link_batches
class Model:
 """两段式假模型：按请求执行阶段返回大纲或分块，并记录每次调用。"""
 def __init__(self,outline,parts):self.outline=outline;self.parts=list(parts);self.calls=[];self.blocks=[]
 def __call__(self,system,user,max_tokens=1400):
  body=json.loads(user);self.calls.append(body['stage'])
  if body['stage']=='outline':return copy.deepcopy(self.outline),{'prompt_tokens':10,'completion_tokens':5}
  if not self.parts:raise RuntimeError('假模型被要求多写一块')
  self.blocks.append(body);value=self.parts.pop(0)
  if isinstance(value,Exception):raise value
  return copy.deepcopy(value),{'prompt_tokens':10,'completion_tokens':5}
class RewriteTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=store.ROOT/'runtime');self.root=Path(self.tmp.name);self.ps=[patch.object(store,'DATA',self.root),patch.object(store,'DB',self.root/'tasks.sqlite3'),patch.object(r.settings,'cloud_key',return_value='fixture')]
  for p in self.ps:p.start()
  store.init();self.id='3'*16;self.row={'id':self.id,'status':'completed','title':'测试','created_at':time.time(),'result':{'text':'注意力是有限的。','segments':[{'text':'注意力是有限的。','start':0,'end':2,'speaker':'说话人1'}]}};store.save(self.row)
  a=FastAPI();a.include_router(r.router);self.c=TestClient(a)
 def tearDown(self):
  for p in reversed(self.ps):p.stop()
  self.tmp.cleanup()
 def raw(self):return {'title':'把注意力留给重要的事','blocks':[{'text':'作者认为，注意力是有限的。','kind':'source','source_ids':['seg-0'],'evidence':'注意力是有限的。'}],'reused_quotes':[],'notes':['素材较短，未扩写凑字']}
 def outline(self,count=1,title='把注意力留给重要的事',budget=0,ids=None):
  return {'title':title,'blocks':[{'heading':f'第{i+1}节','source_ids':ids or ['seg-0'],'budget':budget} for i in range(count)],'notes':[]}
 def part(self,text='作者认为，注意力是有限的。',kind='source',evidence='注意力是有限的。',quotes=None):
  return {'blocks':[{'text':text,'kind':kind,'source_ids':['seg-0'],'evidence':evidence}],'reused_quotes':quotes or [],'notes':[]}
 def test_four_styles_cache_edit_conflict_and_source_unchanged(self):
  before=copy.deepcopy(store.get(self.id)['result'])
  with patch.object(organizer,'request_json',side_effect=Model(self.outline(1),[self.part()]*4)) as m:
   versions=[r.submit(self.id,s) for s in r.STYLES];self.assertTrue(all(v['status']=='completed' for v in versions));self.assertEqual(m.call_count,8)
   for s in r.STYLES:r.submit(self.id,s)
   self.assertEqual(m.call_count,8)
  v=versions[0];res=self.c.put('/api/rewrites/'+v['id'],json={'revision':0,'text':'我的编辑稿'});self.assertEqual(res.status_code,200)
  self.assertEqual(self.c.put('/api/rewrites/'+v['id'],json={'revision':0,'text':'旧窗口覆盖'}).status_code,409)
  with patch.object(organizer,'request_json') as m:self.assertEqual(r.submit(self.id,v['style'])['text'],'我的编辑稿');m.assert_not_called()
  self.assertIn('作者认为',r.get(v['id'])['original']);self.assertEqual(self.c.get('/api/rewrites/'+v['id']+'/markdown').text,'我的编辑稿');self.assertEqual(store.get(self.id)['result'],before)
 def test_invalid_evidence_extension_and_quote(self):
  p=r.context(self.id)
  for field,value in [('evidence','不存在'),('kind','other')]:
   raw=self.raw();raw['blocks'][0][field]=value;self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
  raw=self.raw();raw['blocks'][0]['kind']='extension';self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu');raw['blocks'][0]['text']='（延伸）可以试着减少输入。';self.assertTrue(r.checked(raw,p,'xiaohongshu'))
  raw=self.raw();raw['reused_quotes']=['虚构金句'];self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
 def test_verified_quote_stale_and_recover(self):
  import documents
  documents.generation_save({'id':'quote','task_id':self.id,'action':'quotes','status':'completed','items':[{'text':'注意力是有限的。'},{'text':'假的'}]})
  self.assertEqual(r.context(self.id)['verified_quotes'],['注意力是有限的。'])
  with patch.object(organizer,'request_json',side_effect=Model(self.outline(1),[self.part(quotes=['注意力是有限的。'])])):
   v=r.submit(self.id,'moments');self.assertEqual(v['status'],'completed');self.assertEqual(v['result']['reused_quotes'],['注意力是有限的。'])
  row=store.get(self.id);row['result']['segments'][0]['text']='原文已改变';store.save(row);self.assertTrue(r.listing(self.id)['versions'][0]['stale'])
  v.update(status='running');r.save(v);r.recover();self.assertEqual(r.get(v['id'])['status'],'failed')
 def test_failure_retry_and_cli_json_cache(self):
  with patch.object(organizer,'request_json',side_effect=Model(self.outline(1),[RuntimeError('fixture failure')])):v=r.submit(self.id,'xiaohongshu');self.assertEqual(v['status'],'failed')
  with patch.object(organizer,'request_json',side_effect=Model(self.outline(1),[self.part()])) as m:v=r.submit(self.id,'xiaohongshu');self.assertEqual(m.call_count,1)
  out=io.StringIO()
  with patch.object(organizer,'request_json') as m,contextlib.redirect_stdout(out):shiwen.main(['rewrite',self.id,'--json']);m.assert_not_called()
  self.assertEqual(json.loads(out.getvalue())['id'],v['id']);self.assertFalse(self.c.get('/api/rewrites/'+v['id']+'/card-payload').json()['implemented'])
 def test_evidence_matches_after_normalization_but_not_different_content(self):
  p=r.context(self.id)
  for evidence in ['注意力是有限的！','注意力是有限的','注意力是有限的.','注 意 力是有限的','注意力是有限的；']:
   raw=self.raw();raw['blocks'][0]['evidence']=evidence;self.assertTrue(r.checked(raw,p,'xiaohongshu') is not None)
  for evidence in ['这句话在原文里不存在','！！！','。。']:
   raw=self.raw();raw['blocks'][0]['evidence']=evidence;self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
 def test_evidence_spans_segments_and_corrects_loose_provenance(self):
  wid='4'*16;store.save({'id':wid,'status':'completed','title':'跨段','created_at':time.time(),'result':{'text':'甲乙。丙丁。','segments':[{'text':'甲乙。','start':0,'end':1,'speaker':''},{'text':'丙丁。','start':1,'end':2,'speaker':''}]}})
  p=r.context(wid);raw=self.raw()
  raw['blocks'][0]={'text':'作者先说甲乙，再说丙丁。','kind':'source','source_ids':['seg-0','seg-1'],'evidence':'甲乙。丙丁。'}
  self.assertEqual(r.checked(raw,p,'xiaohongshu')['blocks'][0]['source_ids'],['seg-0','seg-1'])
  raw['blocks'][0]['source_ids']=['seg-1','seg-0'];self.assertTrue(r.checked(raw,p,'xiaohongshu'))
  raw['blocks'][0]['source_ids']=['seg-1'];result=r.checked(raw,p,'xiaohongshu')
  self.assertEqual(result['blocks'][0]['source_ids'],['seg-0','seg-1']);self.assertIn('已按原文实际位置校正',''.join(result['notes']))
  raw['blocks'][0]['evidence']='原文完全没有的句子';self.assertRaises(ValueError,r.checked,raw,p,'xiaohongshu')
 def test_moments_over_limit_truncates_but_other_platforms_reject(self):
  p=r.context(self.id)
  over=self.raw();over['title']='短题';over['blocks']=[{'text':'今天聊到一个很关键的话题。'*40,'kind':'source','source_ids':['seg-0'],'evidence':'注意力是有限的。'}]
  result=r.checked(over,p,'moments')
  self.assertLess(result['character_count']+len(result['title']),100);self.assertIn('正文超平台上限已截断',result['notes'])
  self.assertTrue(all('（延伸）' in b['text'] for b in result['blocks'] if b.get('kind')=='extension'))
  extension=self.raw();extension['blocks']=[{'text':('可以试着减少输入。'*20)+'（延伸）','kind':'extension','source_ids':['seg-0'],'evidence':'注意力是有限的。'}]
  self.assertRaises(ValueError,r.checked,extension,p,'moments')
  zhihu=self.raw();zhihu['blocks']=[{'text':'长'*1600,'kind':'source','source_ids':['seg-0'],'evidence':'注意力是有限的。'}]
  self.assertRaises(ValueError,r.checked,zhihu,p,'zhihu')
 def test_two_stage_budget_split_trims_blocks_to_platform_limit(self):
  model=Model(self.outline(2,budget=2000),[self.part('甲'*2000),self.part('乙'*2000)])
  with patch.object(organizer,'request_json',side_effect=model):v=r.submit(self.id,'gongzhonghao')
  self.assertEqual(v['status'],'completed');self.assertEqual(model.calls,['outline','block','block'])
  self.assertEqual([b['budget'] for b in v['plan']['blocks']],[1250,1250]);self.assertEqual(sum(b['budget'] for b in v['plan']['blocks']),2500)
  self.assertEqual([b['budget'] for b in model.blocks],[1250,1250])
  result=v['result'];self.assertEqual(result['character_count'],2500);self.assertLessEqual(result['character_count'],2500)
  self.assertEqual([s['budget'] for s in result['sections']],[1250,1250]);self.assertEqual([s['characters'] for s in result['sections']],[1250,1250])
  self.assertIn('2个段落超出本块预算已截断',''.join(result['notes']));self.assertIn('块预算合计4000字',''.join(result['notes']))
  self.assertEqual(result['calls'],3)
 def test_outline_invalid_ids_dropped_and_empty_outline_rejected(self):
  outline=self.outline(1);outline['blocks']=[{'heading':'坏','source_ids':['seg-99'],'budget':100},{'heading':'好','source_ids':['seg-0'],'budget':100}]
  with patch.object(organizer,'request_json',side_effect=Model(outline,[self.part()])) as m:v=r.submit(self.id,'zhihu')
  self.assertEqual(v['status'],'completed');self.assertEqual(m.call_count,2);self.assertIn('1个结构块缺少有效来源',''.join(v['result']['notes']))
  bad=self.outline(1);bad['blocks']=[{'heading':'坏','source_ids':['seg-9'],'budget':100}]
  other='5'*16;store.save({**self.row,'id':other})
  model=Model(bad,[])
  with patch.object(organizer,'request_json',side_effect=model):out=r.submit(other,'zhihu')
  self.assertEqual(out['status'],'failed');self.assertIn('大纲没有可用来源块',out['error']);self.assertEqual(model.calls,['outline'])
 def test_failed_block_retry_only_fetches_missing_block(self):
  first=Model(self.outline(2),[self.part('甲'*10),RuntimeError('第二块失败')])
  with patch.object(organizer,'request_json',side_effect=first):v=r.submit(self.id,'zhihu')
  self.assertEqual(v['status'],'failed');self.assertEqual(first.calls,['outline','block','block']);self.assertIn('0',r.get(v['id'])['parts'])
  second=Model(self.outline(2),[self.part('乙'*10)])
  with patch.object(organizer,'request_json',side_effect=second):v=r.submit(self.id,'zhihu')
  self.assertEqual(v['status'],'completed');self.assertEqual(second.calls,['block']);self.assertEqual(len(v['result']['blocks']),2)
 def test_quota_preflight_stops_before_blocks_and_resume_keeps_outline(self):
  model=Model(self.outline(2),[self.part(),self.part()])
  with patch.object(organizer,'request_json',side_effect=model),patch.object(link_batches,'quota',side_effect=[{'remaining':5,'limit':30,'day':'d'},{'remaining':1,'limit':30,'day':'d'}]):
   v=r.submit(self.id,'zhihu')
  self.assertEqual(v['status'],'failed');self.assertIn('次日重试不会重复生成大纲',v['error']);self.assertEqual(model.calls,['outline'])
  resumed=Model(self.outline(2),[self.part(),self.part()])
  with patch.object(organizer,'request_json',side_effect=resumed),patch.object(link_batches,'quota',return_value={'remaining':5,'limit':30,'day':'d'}):
   v=r.submit(self.id,'zhihu')
  self.assertEqual(v['status'],'completed');self.assertEqual(resumed.calls,['block','block'])
 def test_moments_single_block_respects_title_plus_body_ceiling(self):
  model=Model(self.outline(1,title='短题'),[self.part('今天聊到一个很关键的话题。'*40)])
  with patch.object(organizer,'request_json',side_effect=model):v=r.submit(self.id,'moments')
  self.assertEqual(v['status'],'completed');self.assertEqual(len(model.calls),2)
  self.assertEqual(v['plan']['total'],99-len('短题'));self.assertLessEqual(v['result']['character_count']+len(v['result']['title']),99)
  self.assertIn('超出本块预算已截断',''.join(v['result']['notes']));self.assertEqual(v['result']['sections'][0]['characters'],91)
 def test_block_evidence_is_still_verbatim_and_raw_kept_on_failure(self):
  bad=self.part(evidence='凭空编造的原文句子')
  with patch.object(organizer,'request_json',side_effect=Model(self.outline(1),[bad])):v=r.submit(self.id,'gongzhonghao')
  self.assertEqual(v['status'],'failed');self.assertEqual(r.get(v['id'])['raw'],bad);self.assertTrue(all('raw' not in x for x in r.listing(self.id)['versions']))
  with patch.object(organizer,'request_json',side_effect=Model(self.outline(1),[self.part()])):v=r.submit(self.id,v['style'])
  self.assertEqual(v['status'],'completed');self.assertNotIn('raw',r.get(v['id']))
 def test_call_limits_and_budget_reservation_per_call(self):
  model=Model(self.outline(2),[self.part('甲'*10),self.part('乙'*10)])
  with patch.object(organizer,'request_json',side_effect=model) as m,patch.object(r.personal_kb,'reserve_budget',return_value=1) as b,patch.object(r.personal_kb,'settle_budget') as s:
   self.assertEqual(r.submit(self.id,'zhihu')['status'],'completed')
  self.assertEqual([c.args[2] for c in m.call_args_list],[1600,min(8000,700+4*750),min(8000,700+4*750)])
  self.assertEqual([c.args[1] for c in b.call_args_list],[1600,min(8000,700+4*750),min(8000,700+4*750)]);self.assertEqual(s.call_count,3)
  self.assertLessEqual(sum(1+r.PLATFORM[style][3] for style in r.STYLES),12)
 def test_legacy_v1_version_listed_without_false_stale(self):
  payload=r.context(self.id);legacy={'id':r.identity(self.id,'xiaohongshu',payload,'rewrite-v1'),'task_id':self.id,'style':'xiaohongshu','status':'completed','text':'# 旧标题\n\n旧正文','revision':0,'result':{'title':'旧标题','blocks':[],'reused_quotes':[],'notes':[]}}
  r.save(legacy);data=r.listing(self.id)
  self.assertEqual(data['plans'],{style:1+r.PLATFORM[style][3] for style in r.STYLES});self.assertLessEqual(sum(data['plans'].values()),12)
  item=next(v for v in data['versions'] if v['id']==legacy['id']);self.assertFalse(item['stale']);self.assertTrue(item['legacy']);self.assertNotIn('xiaohongshu',data['cached_styles'])
if __name__=='__main__':unittest.main()
