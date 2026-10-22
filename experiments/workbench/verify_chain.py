"""HTTP workbench acceptance. Use an isolated core service and a genuine short file.

Optional --with-ai performs one paid, non-search explanation using the service's
existing configuration. No API keys are accepted on the command line or saved here.
"""
import argparse
import json
import time
from pathlib import Path
import httpx


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--file',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8769)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--with-ai',action='store_true')
    parser.add_argument('--timeout',type=int,default=240,help='Observation timeout; increase explicitly for genuine long samples')
    args=parser.parse_args()
    if not args.file.is_file():parser.error('sample file missing')
    with httpx.Client(base_url=f'http://127.0.0.1:{args.port}',trust_env=False,timeout=90) as c:
        health=c.get('/api/health').json()
        assert health['profile']=='core' and health['models_ready']
        if args.with_ai:assert health['settings']['key_configured']
        started=time.monotonic()
        response=c.post('/api/files/uploads',json={'filename':args.file.name,'size_bytes':args.file.stat().st_size});response.raise_for_status()
        with args.file.open('rb') as f:response=c.put('/api/files/uploads/'+response.json()['upload_id'],content=f,headers={'Content-Length':str(args.file.stat().st_size)})
        response.raise_for_status();ident=response.json()['id']
        while True:
            task=c.get('/api/tasks/'+ident).json()
            if task['status'] in {'completed','failed','waiting_space'}:break
            if time.monotonic()-started>args.timeout:raise RuntimeError('transcription timeout')
            time.sleep(.5)
        assert task['status']=='completed',task.get('message')
        raw=task['result']['text'];doc=c.get('/api/studio/documents/'+ident).json()
        audio=c.get('/api/studio/documents/'+ident+'/audio',headers={'Range':'bytes=0-1023'})
        assert audio.status_code==206 and len(audio.content)==1024
        content=doc['content'];content['content'].append({'type':'paragraph','content':[{'type':'text','text':'工作台验收：保留原话，补充自己的理解。'}]})
        saved=c.put('/api/studio/documents/'+ident,json={'revision':doc['revision'],'content':content});saved.raise_for_status();revision=saved.json()['revision']
        selection=''.join(s['text'] for s in doc['sources'][2:5])[:1000] or doc['sources'][0]['text'][:1000]
        note=c.post('/api/studio/research/documents/'+ident+'/manual-note',json={'basis':'original','revision':revision,'selection':selection,'topic_title':'工作台验收','personal':'用自己的话记录前提与疑问。'});note.raise_for_status()
        exported=c.get('/api/studio/research/notes/'+note.json()['id']+'/export');assert exported.status_code==200 and '未调用AI' in exported.text
        record={'task_id':ident,'duration':task['duration'],'audio_range_status':audio.status_code,'draft_revision':revision,
                'manual_note_id':note.json()['id'],'keys_configured':health['settings']['key_configured'],'with_ai':args.with_ai}
        if args.with_ai:
            response=c.post('/api/studio/research/documents/'+ident,json={'basis':'original','revision':revision,'selection':selection,'question':'解释这段话的逻辑和适用前提，区分经历、陈述与观点。','mode':'explain','online':False});response.raise_for_status();job_id=response.json()['id'];ai_start=time.monotonic()
            while True:
                job=c.get('/api/studio/research/jobs/'+job_id).json()
                if job['status'] in {'completed','failed','cancelled'}:break
                if time.monotonic()-ai_start>240:raise RuntimeError('AI observation timeout')
                time.sleep(1)
            assert job['status']=='completed',job.get('error')
            ai_note=c.post('/api/studio/research/notes',json={'job_id':job_id,'topic_title':'工作台验收','personal':'保留来源与不确定性，后续再验证。'});ai_note.raise_for_status()
            record.update(research_job=job_id,ai_note_id=ai_note.json()['id'],sections=len(job['sections']),usage=job['usage'])
        draft=c.get('/api/studio/documents/'+ident+'/export/json');draft.raise_for_status()
        assert draft.json()['source']['original_name']==args.file.name
        assert c.get('/api/tasks/'+ident).json()['result']['text']==raw
        record.update(raw_unchanged=True,exported=True,seconds=round(time.monotonic()-started,3))
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(record,indent=2),encoding='utf-8')
        print(json.dumps(record))


if __name__=='__main__':main()
