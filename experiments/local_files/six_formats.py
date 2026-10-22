"""Replay six container formats against an isolated core HTTP service.

Pass a genuine short Chinese WAV with --sample; generated video frames are fixture
images only. Voice is never synthesized. Records contain metrics, not transcript text.
"""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
import httpx


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sample',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--port',type=int,default=8767)
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    records=[]
    with httpx.Client(base_url=f'http://127.0.0.1:{args.port}',trust_env=False,timeout=180) as client:
        assert client.get('/api/health').json()['profile']=='core'
        for ext in ['wav','flac','mp3','m4a','mp4','mov']:
            file=args.output/('speech.'+ext)
            command=['ffmpeg','-nostdin','-v','error','-y']
            if ext in {'mp4','mov'}:
                command+=['-f','lavfi','-i','color=c=blue:s=160x90:r=10','-i',str(args.sample),'-map','0:v:0','-map','1:a:0','-shortest','-c:v','mpeg4','-c:a','aac']
            else:
                command+=['-i',str(args.sample)]
                if ext=='m4a':command+=['-c:a','aac']
            command+=['-ac','1','-ar','16000',str(file)]
            subprocess.run(command,check=True,capture_output=True)
            size=file.stat().st_size;start=time.monotonic()
            r=client.post('/api/files/uploads',json={'filename':file.name,'size_bytes':size});r.raise_for_status()
            with file.open('rb') as stream:r=client.put('/api/files/uploads/'+r.json()['upload_id'],content=stream,headers={'Content-Length':str(size)})
            r.raise_for_status();admission=r.json();ident=admission['id']
            while True:
                task=client.get('/api/tasks/'+ident).json()
                if task['status'] in {'completed','failed','waiting_space'} and not task.get('media_restore_pending'):break
                if time.monotonic()-start>180:raise RuntimeError('sample timeout')
                time.sleep(.2)
            assert task['status']=='completed',task.get('message')
            records.append({'format':ext,'input_bytes':size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                            'task_id':ident,'cached_admission':admission['cached'],'status':task['status'],'duration':task['duration'],
                            'segments':len(task['result']['segments']),'text_chars':len(task['result']['text']),
                            'engine':task['result']['engine'],'asr_seconds':task['result']['asr_seconds'],
                            'segments_reused':task['result']['segments_reused'],
                            'seconds':round(time.monotonic()-start,3),'has_video':task['media_info']['has_video']})
            print(json.dumps(records[-1]),flush=True)
            (args.output/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    (args.output/'results.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


if __name__=='__main__':main()
