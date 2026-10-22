"""Explicit one-episode HTTP acceptance; only use an isolated test data directory.

Example: --feed https://pythonbytes.fm/episodes/rss --title '#501' --mode text
No keys accepted here. No automatic AI calls or batch subscriptions.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--feed',required=True)
    parser.add_argument('--title',required=True,help='Unique substring; ambiguous matches are rejected')
    parser.add_argument('--mode',choices=('text','audio'),required=True)
    parser.add_argument('--port',type=int,default=8772)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with httpx.Client(base_url=f'http://127.0.0.1:{args.port}',trust_env=False,timeout=60) as c:
        assert c.get('/api/health').json()['profile']=='core'
        response=c.post('/api/podcasts/feeds',json={'url':args.feed});response.raise_for_status();feed=response.json()
        matches=[e for e in feed['episodes'] if args.title in e['title']]
        if len(matches)!=1:parser.error('title must match exactly one episode; refine --title')
        episode=matches[0];start=time.monotonic()
        response=c.post('/api/podcasts/imports',json={'feed_id':feed['id'],'episode_id':episode['id'],'mode':args.mode});response.raise_for_status();ident=response.json()['id']
        while True:
            job=c.get('/api/podcasts/imports/'+ident).json()
            if job['status'] in ('accepted','failed','waiting_space','interrupted','cancelled'):break
            if time.monotonic()-start>1800:raise RuntimeError('capture observation timeout')
            time.sleep(1)
        assert job['status']=='accepted',job.get('error');task_id=job['task_id']
        while True:
            task=c.get('/api/tasks/'+task_id).json()
            if task['status'] in ('completed','failed','waiting_space'):break
            if time.monotonic()-start>3600:raise RuntimeError('ASR observation timeout')
            time.sleep(1)
        assert task['status']=='completed',task.get('error');raw=task['result']
        doc=c.get('/api/studio/documents/'+task_id).json()
        doc['content']['content'].append({'type':'paragraph','content':[{'type':'text','text':'RSS验收：保留来源，区分原文和自己的理解。'}]})
        saved=c.put('/api/studio/documents/'+task_id,json={'revision':doc['revision'],'content':doc['content']});saved.raise_for_status()
        note=c.post('/api/studio/research/documents/'+task_id+'/manual-note',json={'basis':'original','revision':saved.json()['revision'],'selection':doc['sources'][0]['text'][:800],'topic_title':'RSS单集验收','personal':'确认自己理解的前提，保留问题。'});note.raise_for_status()
        assert c.get('/api/studio/research/notes/'+note.json()['id']+'/export').status_code==200
        for kind in ('json','txt'):assert c.get('/api/studio/documents/'+task_id+'/export/'+kind).status_code==200
        assert c.get('/api/tasks/'+task_id).json()['result']==raw
        report={'task_id':task_id,'import_id':ident,'title':episode['title'],'mode':args.mode,
                'characters':len(raw['text']),'source_kind':task['source']['kind'],
                'engine':raw['engine'],'revision':saved.json()['revision'],'note_id':note.json()['id'],
                'source_hash':hashlib.sha256(raw['text'].encode()).hexdigest(),
                'raw_unchanged':True,'exports':True,'seconds':round(time.monotonic()-start,3)}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':main()
