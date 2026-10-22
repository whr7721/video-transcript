"""Streaming command-line client for the local-only file API."""
import argparse
import json
import time
from pathlib import Path
import httpx


def main():
    parser=argparse.ArgumentParser(description='把本地音视频提交至已启动的拾文核心服务')
    parser.add_argument('file',type=Path)
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--wait',action='store_true',help='等待转写完成')
    args=parser.parse_args()
    if not args.file.is_file() or not 0<args.file.stat().st_size<=1_000_000_000:
        parser.error('请选择 1GB 以内的非空本地文件')
    ident=None;accepted=False
    with httpx.Client(base_url=f'http://127.0.0.1:{args.port}',trust_env=False,timeout=180) as client:
        try:
            response=client.post('/api/files/uploads',json={'filename':args.file.name,'size_bytes':args.file.stat().st_size})
            response.raise_for_status();ident=response.json()['upload_id']
            with args.file.open('rb') as stream:
                response=client.put('/api/files/uploads/'+ident,content=stream,headers={'Content-Length':str(args.file.stat().st_size)})
            response.raise_for_status();result=response.json();accepted=True
            print(json.dumps(result,ensure_ascii=True),flush=True)
            if args.wait:
                while True:
                    response=client.get('/api/tasks/'+result['id']);response.raise_for_status();task=response.json()
                    print(json.dumps({k:task.get(k) for k in ('id','status','stage','progress','message')},ensure_ascii=True),flush=True)
                    if task['status'] in {'completed','failed','waiting_space'}:break
                    time.sleep(2)
        finally:
            if ident and not accepted:
                try:client.delete('/api/files/uploads/'+ident)
                except httpx.HTTPError:pass


if __name__=='__main__':main()
