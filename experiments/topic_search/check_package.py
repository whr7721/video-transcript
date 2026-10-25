"""Repeatable candidate archive and clean unpacked no-key search smoke."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import build_core_package as builder

first=builder.build(ROOT/'runtime/k1-production/package')
second=builder.build(ROOT/'runtime/k1-production/repeat-package')
assert first['sha256']==second['sha256']
with tempfile.TemporaryDirectory(prefix='k1-package-') as temporary:
    root=Path(temporary)
    with zipfile.ZipFile(first['archive']) as archive:archive.extractall(root/'package')
    package=root/'package'
    files=builder.verify_manifest(package)
    env=dict(os.environ)
    for key in ('SILICONFLOW_API_KEY','DEEPSEEK_API_KEY','SHIWEN_DATA_DIR','SHIWEN_PROFILE'):env.pop(key,None)
    env['SHIWEN_CORE_DATA_DIR']=str(root/'core-data')
    env['PYTHONIOENCODING']='utf-8'
    code='''
import app_core,store
from fastapi.testclient import TestClient
task={'id':'aaaaaaaaaaaaaaaa','status':'completed','created_at':0,'title':'验收样本',
      'source':{'kind':'local_file','original_name':'fixture.wav'},
      'result':{'segments':[{'text':'公开过程吸引客户，AI工具需要真实交付。','start':0,'end':5}]}}
with TestClient(app_core.app) as client:
 store.save(task)
 assert not client.get('/api/settings').json()['key_configured']
 r=client.post('/api/studio/research/documents/'+task['id']+'/manual-note',json={'selection':'公开过程','personal':'我的交付理解','topic_title':'验收专题'})
 assert r.status_code==200,r.text
 note=r.json();topic=note['topic_id']
 base='/api/studio/research/topics/'+topic+'/search'
 r=client.get(base,params={'q':'交付'});assert r.status_code==200,r.text
 hit=next(h for h in r.json()['items'] if h['category']=='personal')
 assert client.post(base+'/context',json={k:hit[k] for k in ('hit_id','source_hash')}).status_code==200
 r=client.put('/api/studio/research/notes/'+note['id'],json={'revision':1,'personal':'更新为柠檬树'})
 assert r.status_code==200,r.text
 assert client.post(base+'/context',json={k:hit[k] for k in ('hit_id','source_hash')}).status_code==409
 assert client.get(base,params={'q':'柠檬'}).json()['items']
 assert client.get('/studio/').status_code==200
 original=store.get(task['id'])['result']
with TestClient(app_core.app) as client:
 assert client.get(base,params={'q':'柠檬'}).json()['items']
 assert store.get(task['id'])['result']==original
print('clean unpacked no-key search/edit/stale/restart OK')
'''
    result=subprocess.run([sys.executable,'-B','-c',code],cwd=package,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
report={'archive':Path(first['archive']).name,'sha256':first['sha256'],'manifest_files':files,
        'same_input_zip_equal':True,'clean_unpacked_no_key_chain':True,
        'edit_stale_and_restart':True,'public_full_directory_gate':True,
        'independent_machine':False,'real_browser_acceptance':False}
(ROOT/'experiments/topic_search/PACKAGE_20261025.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
