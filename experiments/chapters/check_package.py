import json,os,subprocess,sys,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import build_core_package as builder
first=builder.build(ROOT/'runtime/r2/package')
second=builder.build(ROOT/'runtime/r2/repeat-package')
assert first['sha256']==second['sha256']
with tempfile.TemporaryDirectory(prefix='r2-package-') as temporary:
 root=Path(temporary)
 with zipfile.ZipFile(first['archive']) as archive:archive.extractall(root/'package')
 package=root/'package';files=builder.verify_manifest(package)
 env=dict(os.environ);env.pop('SILICONFLOW_API_KEY',None);env.pop('DEEPSEEK_API_KEY',None)
 env['SHIWEN_CORE_DATA_DIR']=str(root/'data');env['PYTHONIOENCODING']='utf-8'
 code='''
import app_core,store
from fastapi.testclient import TestClient
with TestClient(app_core.app) as c:
 store.save({'id':'aaaaaaaaaaaaaaaa','status':'completed','created_at':0,'result':{'text':'本地正文。'}})
 base='/api/studio/documents/aaaaaaaaaaaaaaaa'
 r=c.get(base+'/chapters');assert r.status_code==200,r.text
 p=r.json();assert c.post(base+'/chapters',json={'revision':0,'plan':p}).status_code==200
 assert c.get(base+'/chapters/0/text').json()['text']=='本地正文。'
 r=c.post(base+'/chapter-jobs',json={'revision':1,'action':'directory'})
 assert r.status_code==400 and 'Key' in r.text,r.text
 print('clean package no-key chapter path OK')
'''
 result=subprocess.run([sys.executable,'-c',code],cwd=package,env=env,capture_output=True,text=True,encoding='utf-8')
 if result.returncode:raise RuntimeError(result.stdout+result.stderr)
report={'manifest_files':files,'same_input_zip_equal':True,'clean_unpacked_no_key_chain':True,'independent_machine':False,'archive':Path(first['archive']).name}
(ROOT/'experiments/chapters/PACKAGE_20261023.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
