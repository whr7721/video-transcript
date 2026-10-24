"""Separate user probes; known sources are diagnostics only, never scoring inputs."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.retrieval import projection,baselines
from experiments.retrieval_rerank.controls import Controls
from experiments.retrieval_rerank.semantic import Semantic
D,_=projection.load('.');parts=projection.passages(D);engine=baselines.Baselines(parts);control=Controls(parts)
manifest=json.loads(Path('experiments/retrieval_rerank/MODEL_MANIFEST.json').read_text(encoding='utf-8'))
model=Semantic('runtime/k1-rerank/model',manifest)
queries=json.loads(Path('runtime/k1/user-queries.json').read_text(encoding='utf-8'))
prior=json.loads(Path('experiments/retrieval/USER_PROBES_20261024.json').read_text(encoding='utf-8'))
rows=[];private=[]
for i,query in enumerate(queries):
 if projection.fingerprint(query)!=prior[i]['query_hash']:raise ValueError('Probe query changed')
 pool=engine.search(query,'bigram_bm25',50)
 semantic,timing=model.rank(query,pool)
 rankings={'bm25':pool,'constraints':control.rank(query,pool,'constraints'),
           'lexical_rerank':control.rank(query,pool,'lexical_rerank'),'semantic_rerank':semantic}
 for method,hits in rankings.items():
  uid=prior[i].get('known_candidate_source')
  row={'probe_id':prior[i]['probe_id'],'query_hash':prior[i]['query_hash'],'method':method,
       'known_candidate_source':uid,'known_candidate_source_rank50':next((j+1 for j,h in enumerate(hits) if h['source_uid']==uid),None) if uid else None,
       'returned_count':len(hits),'top5_ids':[h['id'] for h in hits[:5]],
       'scope':'known source can be partial; not gold and not answer accuracy'}
  rows.append(row);private.append({'query':query,'method':method,'rankings':hits})
 print('probe',i+1,'semantic_seconds',round(timing['seconds'],3),flush=True)
engine.close()
Path('experiments/retrieval_rerank/USER_PROBES_20261024.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
Path('runtime/k1-rerank/user-review.json').write_text(json.dumps(private,ensure_ascii=False,indent=2),encoding='utf-8')
