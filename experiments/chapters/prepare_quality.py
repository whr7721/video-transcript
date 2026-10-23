"""Prepare review candidates, not a semantic quality pass."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import os
os.environ['SHIWEN_DATA_DIR']=str(ROOT/'runtime/r2-a/preview-data')
import store,chapters
out=ROOT/'runtime/r2/quality';out.mkdir(parents=True,exist_ok=True)
metadata=[]
for ident in ('8235b98d9f210623','b33db03eb1b9a504','34b3090a47421637'):
 task=store.get(ident);view=chapters.snapshot(task);plan=chapters.get(task);parts=chapters.fragments(view)
 rows=[]
 for n in range(10):
  part=parts[round((len(parts)-1)*n/9)]
  chapter=next((i,s) for i,s in enumerate(plan['sections']) if part['id'] in s['fragment_ids'])
  rows.append({'candidate':n+1,'fragment_id':part['id'],'chapter_index':chapter[0],
               'title':chapter[1]['title'],'guide':chapter[1].get('guide',''),
               'original_excerpt':part['text'],'human_helpful':None,'new_claims':None,'conditions_preserved':None})
 (out/(ident+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 metadata.append({'task_id':ident,'candidate_locations':10,'sampling':'uniform head/middle/tail; not a semantic gold set','status':'pending human quality review'})
(ROOT/'experiments/chapters/QUALITY_20261023.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print('Prepared 30 source/guide pairs; no model calls')
