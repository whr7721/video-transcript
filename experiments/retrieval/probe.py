"""Probe new user queries without changing frozen benchmark labels or rankings."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from experiments.retrieval import projection,baselines

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--queries',required=True);parser.add_argument('--root',default='.');parser.add_argument('--output',default='runtime/k1/user-probes.results.json');args=parser.parse_args()
 queries=json.loads(Path(args.queries).read_text(encoding='utf-8'))
 if not isinstance(queries,list) or len(queries)>50:raise ValueError('Expected up to 50 queries')
 docs,_=projection.load(args.root);engine=baselines.Baselines(projection.passages(docs));result=[]
 try:
  for query in queries:
   result.append({'query':query,'query_hash':projection.fingerprint(query),'method':'bigram_bm25',
                  'hits':engine.search(query,'bigram_bm25',50),'annotation':'unjudged; not part of frozen accuracy'})
 finally:engine.close()
 output=Path(args.output).resolve();allowed=(Path(args.root)/'runtime').resolve()
 if not output.is_relative_to(allowed):raise ValueError('Probe output contains private text; choose a runtime path')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Wrote',len(result),'private probe results; no labels or query-specific parameters changed')
