"""Freeze labels against exact source snapshots before measuring any retrieval run."""
import argparse
import json
from pathlib import Path
import projection


def freeze(root,spec_path,output):
 docs,manifest=projection.load(root);by_id={d['uid']:d for d in docs};cases=[]
 for spec in json.loads(Path(spec_path).read_text(encoding='utf-8')):
  case={k:v for k,v in spec.items() if k!='targets'};case['gold']=[]
  for target in spec['targets']:
   doc=by_id[target['source_uid']];found=False
   for block in doc['blocks']:
    if target.get('block_id') and block['id']!=target['block_id']:continue
    start=block['text'].find(target['anchor'])
    if start<0:continue
    case['gold'].append({'source_uid':doc['uid'],'source_hash':doc['source_hash'],
                         'block_id':block['id'],'start':start,'end':start+len(target['anchor']),
                         'evidence_hash':projection.fingerprint(target['anchor'])})
    found=True
   if not found:raise ValueError('Missing anchor for '+spec['id']+' in '+target['source_uid'])
  cases.append(case)
 dataset={'schema_version':1,'annotation':'author-prepared candidate labels, not user-reviewed gold',
          'corpus_hash':projection.fingerprint(manifest),'corpus':manifest,'cases':cases}
 Path(output).write_text(json.dumps(dataset,ensure_ascii=False,indent=2),encoding='utf-8')
 return dataset

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',default='.');parser.add_argument('--spec',required=True);parser.add_argument('--output',required=True)
 args=parser.parse_args();v=freeze(args.root,args.spec,args.output);print('Frozen',len(v['cases']),'questions against',len(v['corpus']),'sources')
