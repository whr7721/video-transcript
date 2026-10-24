"""Same-pool constraint/lexical/semantic comparison, with per-paraphrase reporting."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.retrieval import projection,baselines,evaluate
from experiments.retrieval_rerank.controls import Controls,VERSION
from experiments.retrieval_rerank.semantic import Semantic
METHODS=('bm25','constraints','lexical_rerank','semantic_rerank')


def first_rank(hits,gold):return next((i+1 for i,h in enumerate(hits) if evaluate.relevant(h,gold)),None)


def compact(hits):return [{'id':p['id'],'source_uid':p['source_uid']} for p in hits[:5]]


def run(root,output):
 root=Path(root).resolve();out=Path(output);out.mkdir(parents=True,exist_ok=True)
 dataset=json.loads((root/'experiments/retrieval/cases_v1.json').read_text(encoding='utf-8'))
 docs,manifest=projection.load(root)
 if projection.fingerprint(manifest)!=dataset['corpus_hash']:raise ValueError('Frozen corpus changed')
 evaluate.validate_labels(docs,dataset);parts=projection.passages(docs);engine=baselines.Baselines(parts);controls=Controls(parts)
 model_manifest=json.loads((root/'experiments/retrieval_rerank/MODEL_MANIFEST.json').read_text(encoding='utf-8'))
 model=Semantic(root/'runtime/k1-rerank/model',model_manifest)
 rows=[];private=[];paraphrases=[]
 cases=[{**case,'is_user_probe':False} for case in dataset['cases']]
 user_path=root/'runtime/k1/user-queries.json'
 if user_path.exists():
  cases.extend({'id':f'user-{i+1:02d}','query':q,'category':'user_probe','split':'separate','gold':[],
                'is_user_probe':True} for i,q in enumerate(json.loads(user_path.read_text(encoding='utf-8'))))
 try:
  for case in cases:
   query=case['query'];gold=case['gold'];pool=engine.search(query,'bigram_bm25',50)
   constrained=controls.rank(query,pool,'constraints');lexical=controls.rank(query,pool,'lexical_rerank')
   semantic,semantic_time=model.rank(query,pool)
   rankings={'bm25':pool,'constraints':constrained,'lexical_rerank':lexical,'semantic_rerank':semantic}
   if any(any(h['id'] not in {p['id'] for p in pool} for h in ranking) for ranking in rankings.values()):raise ValueError('Candidate pool injection')
   case_rows=[]
   for method,hits in rankings.items():
    row={'case_id':case['id'],'category':case['category'],'split':case['split'],'method':method,
         'candidate_pool_size':len(pool),'returned_pool_size':len(hits),'top5':compact(hits),
         'semantic_timing':semantic_time if method=='semantic_rerank' else None}
    if case['is_user_probe']:row.update(query_hash=projection.fingerprint(query),annotation='unjudged separate probe')
    else:
     row.update(evaluate.score(hits[:5],gold))
     if gold:row.update(first_known_rank50=first_rank(hits,gold),in_original_pool50=first_rank(pool,gold) is not None)
    rows.append(row);case_rows.append(row)
    private.append({'case_id':case['id'],'query':query,'method':method,'top5':hits[:5]})
   if case['category']=='paraphrase':paraphrases.append({'case_id':case['id'],'query':query,'rows':case_rows})
   print(case['id'], 'pool',len(pool),'semantic',round(semantic_time['seconds'],3),'seconds',flush=True)
  summary=[]
  for split in ('dev','heldout','all'):
   for method in METHODS:
    selected=[r for r in rows if r['method']==method and r['category']!='user_probe' and (split=='all' or r['split']==split)]
    positive=[r for r in selected if 'evidence_success' in r];negative=[r for r in selected if 'nonempty' in r]
    summary.append({'split':split,'method':method,'positives':len(positive),'evidence_hits5':sum(r['evidence_success'] for r in positive),
                    'known_mrr5':sum(r['known_mrr'] for r in positive)/len(positive),
                    'source_hits5':sum(r['source_success'] for r in positive),
                    'negative_nonempty':sum(r['nonempty'] for r in negative),'negatives':len(negative),
                    'filter_lost_known_evidence':sum(r['in_original_pool50'] and r['first_known_rank50'] is None for r in positive)})
  categories=[]
  for category in sorted({r['category'] for r in rows}-{'no_answer','user_probe'}):
   for method in METHODS:
    selected=[r for r in rows if r['method']==method and r['category']==category]
    categories.append({'category':category,'method':method,'cases':len(selected),'hits5':sum(r['evidence_success'] for r in selected)})
  report={'controls_version':VERSION,'dataset_hash':projection.fingerprint(dataset),'corpus_hash':dataset['corpus_hash'],
          'model_manifest':model_manifest,'model_load_seconds':model.load_seconds,'onnxruntime':model.ort_version,
          'semantic_total_seconds':sum(r['semantic_timing']['seconds'] for r in rows if r['semantic_timing']),
          'paid_api_calls':0,'vector_database':False,'candidate_pool':'unchanged BM25 Top50','summary':summary,'categories':categories,'per_case':rows}
  (out/'RESULTS_20261024.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
  (out/'PARAPHRASE_20261024.json').write_text(json.dumps(paraphrases,ensure_ascii=False,indent=2),encoding='utf-8')
  private_dir=root/'runtime/k1-rerank';private_dir.mkdir(parents=True,exist_ok=True)
  (private_dir/'review.json').write_text(json.dumps(private,ensure_ascii=False,indent=2),encoding='utf-8')
  lines=['# Paraphrase逐题对照','使用既有候选标签；v1留出已公开，本轮为回归，不是新盲测。','原始BM25 Top50中四题均有已标注位置；约束方法丢失的位置属于过滤损失。','',
         '| 题目 | BM25 | 约束 | 词法重排 | 语义重排 |','| --- | --- | --- | --- | --- |']
  for item in paraphrases:
   labels=[]
   for r in item['rows']:
    rank=r.get('first_known_rank50');labels.append(('命中' if r['evidence_success'] else '失分')+' / '+('第'+str(rank)+'名' if rank else ('过滤后无已标注位置' if r['method']=='constraints' else '原始池无已标注位置')))
   lines.append('| '+item['query']+' | '+' | '.join(labels)+' |')
  (out/'PARAPHRASE_20261024.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 finally:engine.close()
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',default='.');parser.add_argument('--output',default='experiments/retrieval_rerank');args=parser.parse_args()
 r=run(args.root,args.output)
 for row in r['summary']:
  if row['split']=='all':print(json.dumps(row),flush=True)
