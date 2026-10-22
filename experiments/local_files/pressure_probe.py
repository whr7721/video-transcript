"""Internal destructive fixture probe: only operates in runtime/v1-b test data.

First submit a genuine two-hour file to an isolated core service and let it complete.
This probe removes that test task's derived WAV, retains its source/cache/results,
replays the queue, and writes 4.7GB of explicitly labelled quota fixtures.
"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--test-data',type=Path,required=True)
    parser.add_argument('--task-id',required=True)
    parser.add_argument('--port',type=int,default=8767)
    parser.add_argument('--pid',type=int,required=True)
    args=parser.parse_args();data=args.test_data.resolve()
    if not data.is_relative_to((ROOT/'runtime/v1-b').resolve()):parser.error('仅允许 runtime/v1-b 内的测试目录')
    if (data/'.core-profile').read_text(encoding='utf-8')!='core-v1':parser.error('缺少核心测试目录标记')
    os.environ['SHIWEN_DATA_DIR']=str(data)
    import httpx,psutil,store,media_buffer
    client=httpx.Client(base_url=f'http://127.0.0.1:{args.port}',trust_env=False,timeout=30)
    assert client.get('/api/health').json()['profile']=='core'
    task=store.get(args.task_id)
    assert task and task['status']=='completed' and task['source']['kind']=='local_file'
    path=data/'jobs'/task['id']
    assert (path/'original.media').is_file() and task['duration']==7200
    (path/'audio.wav').unlink(missing_ok=True)
    task.update(status='failed',stage='failed');store.save(task)
    media_buffer.state(task['id'],'awaiting_review')
    fixtures=[];report={'capacity_bytes':media_buffer.CAPACITY,'snapshots':[],'fixture_kind':'real_written_bytes_not_audio','warm_cache_replay':True}
    for c,size,state,pin,lease in [('1',10**9,'awaiting_review',False,False),('2',10**9,'finalized',True,False),('3',10**9,'finalized',False,True),('4',10**9,'active',False,False),('5',600_000_000,'awaiting_review',False,False),('6',100_000_000,'finalized',False,False)]:
        ident=c*16;old=store.get(ident)
        assert not old or old.get('source',{}).get('kind')=='quota_fixture'
        directory=data/'jobs'/ident;directory.mkdir(exist_ok=True)
        file=directory/'original.media';block=bytes(4*1024*1024);remaining=size
        with file.open('wb',buffering=0) as f:
            while remaining:
                n=min(remaining,len(block));f.write(memoryview(block)[:n]);remaining-=n
        assert not getattr(file.stat(),'st_file_attributes',0)&(0x200|0x800)
        store.save({'id':ident,'source':{'kind':'quota_fixture'},'title':'quota fixture','status':'completed','created_at':0})
        media_buffer.register(ident,pin);media_buffer.state(ident,state)
        if lease:media_buffer.touch(ident)
        fixtures.append({'id':ident,'bytes':size,'state':state,'pinned':pin,'leased':lease})
    report['fixtures']=fixtures
    report['snapshots'].append({'phase':'before_conversion',**media_buffer.public()})
    stop=threading.Event();peak={'physical_bytes':0,'reserved_bytes':0,'combined_bytes':0,'rss_bytes':0,'samples':0};process=psutil.Process(args.pid)
    def monitor():
        while not stop.is_set():
            q=media_buffer.public();peak['samples']+=1
            for name,key in [('physical_bytes','used_bytes'),('reserved_bytes','reserved_bytes')]:peak[name]=max(peak[name],q[key])
            peak['combined_bytes']=max(peak['combined_bytes'],q['used_bytes']+q['reserved_bytes'])
            try:peak['rss_bytes']=max(peak['rss_bytes'],sum(p.memory_info().rss for p in [process]+process.children(recursive=True)))
            except psutil.Error:pass
            stop.wait(.05)
    thread=threading.Thread(target=monitor);thread.start();started=time.monotonic()
    try:
        client.post('/api/files/tasks/'+task['id']+'/retry').raise_for_status()
        while True:
            current=client.get('/api/tasks/'+task['id']).json()
            if current['status'] in {'waiting_space','failed','completed'}:break
            if time.monotonic()-started>60:raise RuntimeError('did not reach quota gate')
            time.sleep(.1)
        assert current['status']=='waiting_space',current.get('message')
        assert not (data/'jobs'/('6'*16)/'original.media').exists()
        assert all((data/'jobs'/f['id']/'original.media').stat().st_size==f['bytes'] for f in fixtures[:-1])
        report['snapshots'].append({'phase':'paused_after_confirmed_cleanup',**media_buffer.public()})
        media_buffer.state('5'*16,'finalized')
        assert client.post('/api/studio/buffer/resume').json()['resumed']==1
        while True:
            current=client.get('/api/tasks/'+task['id']).json()
            if current['status'] in {'completed','failed','waiting_space'}:break
            if time.monotonic()-started>900:raise RuntimeError('cache replay timeout')
            time.sleep(.2)
        assert current['status']=='completed',current.get('message')
        assert all((data/'jobs'/f['id']/'original.media').is_file() for f in fixtures[:4])
        report['snapshots'].append({'phase':'completed',**media_buffer.public()})
        report.update(task_id=task['id'],duration=current['duration'],preparation_seconds=current.get('preparation_seconds'),
                      total_seconds=round(time.monotonic()-started,3),segments_reused=current['result']['segments_reused'],
                      segments=len(current['result']['segments']),peak=peak)
        assert peak['combined_bytes']<=media_buffer.CAPACITY
        assert report['segments_reused']==report['segments']>0
        target=ROOT/'runtime/v1-b/pressure-final.json';target.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report),flush=True)
    finally:
        stop.set();thread.join();client.close()
        for f in fixtures:(data/'jobs'/f['id']/'original.media').unlink(missing_ok=True)


if __name__=='__main__':main()
