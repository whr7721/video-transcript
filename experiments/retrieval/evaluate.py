"""Evaluate fixed lexical systems. Never calls a model or writes original databases."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.retrieval import baselines,projection


def relevant(passage,gold):
 return any(passage['source_uid']==g['source_uid'] and passage['source_hash']==g['source_hash']
            and any(r['block_id']==g['block_id'] and r['start']<=g['start'] and r['end']>=g['end'] for r in passage['ranges']) for g in gold)


def score(hits,gold):
 if not gold:return {'nonempty':bool(hits)}
 ranks=[i+1 for i,p in enumerate(hits) if relevant(p,gold)]
 return {'evidence_success':bool(ranks),'source_success':any(p['source_uid'] in {g['source_uid'] for g in gold} for p in hits),
         'known_mrr':1/min(ranks) if ranks else 0.0}


def validate_labels(docs,dataset):
 by_id={d['uid']:d for d in docs}
 for case in dataset['cases']:
  for gold in case['gold']:
   doc=by_id[gold['source_uid']]
   if doc['source_hash']!=gold['source_hash']:raise ValueError('Frozen source changed; do not silently relabel')
   text=next(b['text'] for b in doc['blocks'] if b['id']==gold['block_id'])
   if not 0<=gold['start']<gold['end']<=len(text) or projection.fingerprint(text[gold['start']:gold['end']])!=gold['evidence_hash']:
    raise ValueError('Invalid frozen evidence range')


def percentile(values,p):
 values=sorted(values)
 return values[min(len(values)-1,max(0,int((len(values)-1)*p)))] if values else None


def evaluate(root,dataset_path,output,repeats=7):
 if type(repeats) is not int or not 1<=repeats<=100:raise ValueError('Invalid repeats')
 dataset=json.loads(Path(dataset_path).read_text(encoding='utf-8-sig'));docs,manifest=projection.load(root)
 if projection.fingerprint(manifest)!=dataset['corpus_hash']:raise ValueError('Corpus changed since freeze')
 validate_labels(docs,dataset);parts=projection.passages(docs)
 assert all(projection.resolve(docs,p)==p['text'] for p in parts)
 started=time.perf_counter();engine=baselines.Baselines(parts);index_ms=(time.perf_counter()-started)*1000
 rows=[];private=['# K1 逐题人工复核材料','候选标签未获用户确认；检索候选不是答案。']
 try:
  for case in dataset['cases']:
   gold=case['gold'];private.extend(['\n## '+case['id']+' '+case['query'],'类别：'+case['category']+'；划分：'+case['split']])
   if not gold:private.append('候选标注：本次文字语料无答案，仍待人工复核。')
   for g in gold:
    d=next(d for d in docs if d['uid']==g['source_uid']);b=next(b for b in d['blocks'] if b['id']==g['block_id'])
    private.extend(['参考位置：'+g['source_uid']+' '+g['block_id'],b['text'][max(0,g['start']-120):g['end']+220]])
   for method in baselines.METHODS:
    times=[];hits=engine.search(case['query'],method)
    for _ in range(repeats):
     started=time.perf_counter();engine.search(case['query'],method);times.append((time.perf_counter()-started)*1000)
    row={'case_id':case['id'],'category':case['category'],'split':case['split'],'method':method,
         **score(hits,gold),'latency_ms':statistics.median(times),
         'top5':[{'id':h['id'],'source_uid':h['source_uid'],'source_hash':h['source_hash'],'ranges':h['ranges']} for h in hits]}
    if gold:row['evidence_in_pool50']=any(relevant(h,gold) for h in engine.search(case['query'],method,50))
    rows.append(row);private.append('\n### '+method+' '+json.dumps({k:v for k,v in row.items() if k not in {'top5'}},ensure_ascii=False))
    for h in hits:private.extend([h['id'],h['text'][:500]])
  summary=[]
  for split in ('dev','heldout','all'):
   for method in baselines.METHODS:
    selected=[r for r in rows if r['method']==method and (split=='all' or r['split']==split)]
    positives=[r for r in selected if 'evidence_success' in r];negative=[r for r in selected if 'nonempty' in r]
    latencies=[r['latency_ms'] for r in selected]
    summary.append({'split':split,'method':method,'answerable':len(positives),
                    'evidence_hits5':sum(r['evidence_success'] for r in positives),
                    'source_hits5':sum(r['source_success'] for r in positives),
                    'known_mrr5':statistics.mean(r['known_mrr'] for r in positives),
                    'no_answer_cases':len(negative),'no_answer_nonempty':sum(r['nonempty'] for r in negative),
                    'warm_query_p50_ms':statistics.median(latencies),'warm_query_p95_ms':percentile(latencies,.95)})
  size=engine.db.execute('PRAGMA page_count').fetchone()[0]*engine.db.execute('PRAGMA page_size').fetchone()[0]
 finally:engine.close()
 report={'schema_version':1,'projection_version':projection.VERSION,'dataset_hash':projection.fingerprint(dataset),
         'corpus_hash':dataset['corpus_hash'],'sources':len(docs),'passages':len(parts),'indexed_characters':sum(len(p['text']) for p in parts),
         'sqlite_version':__import__('sqlite3').sqlite_version,'index_build_ms':index_ms,'in_memory_db_bytes':size,
         'paid_calls':0,'new_dependencies':[],'annotation':dataset['annotation'],
         'limits':['candidate labels not user-reviewed','no generated answers','warm small-corpus timings only','unjudged results are not proven irrelevant','ASR intent needs listening confirmation'],
         'summary':summary,'per_case':rows}
 Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 private_dir=Path(root)/'runtime/k1';private_dir.mkdir(parents=True,exist_ok=True)
 (private_dir/'REVIEW.md').write_text('\n\n'.join(private),encoding='utf-8')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',default='.');parser.add_argument('--cases',default='experiments/retrieval/cases_v1.json');parser.add_argument('--output',default='experiments/retrieval/RESULTS_20261024.json');args=parser.parse_args()
 result=evaluate(args.root,args.cases,args.output)
 print(json.dumps({k:result[k] for k in ('sources','passages','indexed_characters','index_build_ms','in_memory_db_bytes')},ensure_ascii=False))
 for row in result['summary']:
  if row['split']=='heldout':print(json.dumps(row,ensure_ascii=False))
