"""Shared ZIP entries for existing tasks; never change source artifacts."""
import re
import store

def write_task(z, item):
    entry={k:item.get(k) for k in ('index','url','status','task_id','job_id','error')}
    entry.update(files=[],missing=[])
    tid=item.get('task_id'); task=store.get(tid) if tid else None
    title=re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',str((task or {}).get('title') or '文稿')).strip(' .')[:60] or '文稿'
    prefix=f"{item['index']:03}-{title}-{tid or 'unresolved'}"
    safe=bool(tid and re.fullmatch('[a-f0-9]{16}',tid))
    for name in ['transcript.txt','transcript.json','transcript.srt','summary.md','mindmap.html']:
        path=store.DATA/'jobs'/tid/name if safe else None
        if path and path.is_file() and item.get('status')!='duplicate':
            z.write(path,prefix+'/'+name);entry['files'].append(name)
        elif name.startswith('transcript.') or item.get('summarize'):entry['missing'].append(name)
    return entry
