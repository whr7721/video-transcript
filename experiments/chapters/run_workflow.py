"""Real HTTP chapter workflow plus same-input legacy comparison; no secrets in output."""
from pathlib import Path
import sys,json,time,hashlib,httpx,os
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ['SHIWEN_DATA_DIR']=str(ROOT/'runtime/r2-a/preview-data')
import store,chapters,documents,manuscript,organizer,settings,chapter_jobs
out=ROOT/'runtime/r2/real-model';out.mkdir(parents=True,exist_ok=True)
ident='8235b98d9f210623';task=store.get(ident)
base='http://127.0.0.1:8774/api/studio/documents/'+ident
results={}
with httpx.Client(trust_env=False,timeout=30) as client:
    doc=client.get(base).json();before=json.dumps(doc['content'],sort_keys=True)
    plan=client.get(base+'/chapters').json()
    view=chapters.snapshot(task)
    candidates=[(i,chapters.resolve(view,plan,i)) for i in range(len(plan['sections']))]
    index,selected=max((x for x in candidates if len(x[1]['text'])<=8000),key=lambda x:len(x[1]['text']))
    results.update(index=index,source_characters=len(selected['text']),chapter_revision=plan['revision'])
    estimate=client.post(base+'/chapter-estimate',json={'action':'clean','revision':plan['revision'],'index':index});estimate.raise_for_status()
    response=client.post(base+'/chapter-jobs',json={'action':'clean','revision':plan['revision'],'index':index});response.raise_for_status();job=response.json()
    while job['status'] in {'queued','running'}:
        time.sleep(1);job=client.get(base+'/chapter-jobs/'+job['id']).json()
    if job['status']!='completed':raise RuntimeError(job.get('error'))
    (out/'chapter-clean.json').write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'chapter-source.txt').write_text(selected['text'],encoding='utf-8')
    results['clean']={k:job.get(k) for k in ('id','status','calls','usage','elapsed_seconds')}
    results['clean']['characters']=len(documents.text(job['content']))
    # Manual note and real AI explain both use exact chapter coordinates.
    text=selected['text'][:500];start=len(text)-len(text.lstrip());text=text.strip()
    basis={'basis':'chapter','revision':doc['revision'],'chapter_revision':plan['revision'],'chapter_index':index,'selection_start':start,'selection':text}
    note=client.post('http://127.0.0.1:8774/api/studio/research/documents/'+ident+'/manual-note',json={**basis,'topic_title':'R2链路验收','personal':'测试笔记：保留章节原话和版本，便于后续核对；不代表用户观点。'});note.raise_for_status()
    note_id=note.json()['id'];export=client.get('http://127.0.0.1:8774/api/studio/research/notes/'+note_id+'/export');export.raise_for_status()
    assert view['source_hash'] in export.text
    results['manual_note']={'id':note_id,'scope_in_export':True}
    answer=client.post('http://127.0.0.1:8774/api/studio/research/documents/'+ident,json={**basis,'mode':'explain','online':False,'question':'这段话的论证、具体例子和适用条件是什么？区分作者观点和事实。'});answer.raise_for_status();answer=answer.json()
    while answer['status'] in {'queued','running'}:
        time.sleep(1);answer=client.get('http://127.0.0.1:8774/api/studio/research/jobs/'+answer['id']).json()
    results['research']={'id':answer['id'],'status':answer['status'],'error':answer.get('error'),'usage':answer.get('usage',[])}
    (out/'chapter-research.json').write_text(json.dumps(answer,ensure_ascii=False,indent=2),encoding='utf-8')
    export=client.get(base+'/chapters/export/md');export.raise_for_status();(out/'chapters.md').write_text(export.text,encoding='utf-8')
    after=client.get(base).json();assert before==json.dumps(after['content'],sort_keys=True)
    results['draft_unchanged']=True
    results['export_has_clean_preview']='整理预览' in export.text
print('HTTP workflow:',json.dumps(results,ensure_ascii=True),flush=True)
# The exact same chapter text is the <=24000 character legacy control.
key=settings.protect(json.loads((ROOT/'data/settings.json').read_text(encoding='utf-8'))['encrypted_key'],decrypt=True)
settings.cloud_key=lambda:key
control={'id':'r2-control','task_id':'r2-control-only','action':'manuscript','status':'running','usage':[]}
control_task={'id':ident,'result':{'text':selected['text'],'segments':[{'text':selected['text']}]}}
start=time.monotonic();manuscript.run(control,control_task,organizer.request_json)
control['status']='completed';documents.generation_save(control)
(out/'legacy-control.json').write_text(json.dumps(control,ensure_ascii=False,indent=2),encoding='utf-8')
results['legacy_control']={'characters':len(documents.text(control['content'])),'usage':control['usage'],'seconds':time.monotonic()-start,'summary_error':control.get('summary_error')}
results['quota_after']=chapter_jobs.quota()
(ROOT/'experiments/chapters/WORKFLOW_20261023.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('COMPLETED',json.dumps(results['quota_after']),flush=True)
