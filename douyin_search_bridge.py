"""Wrapper reuses the existing metadata search without changing its project/config."""
import argparse,asyncio,importlib.util,json,os
from pathlib import Path
PROFILE=Path(os.environ['SHIWEN_DATA_DIR']).resolve()/'browser'
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
if not (PROFILE/'Default').is_dir():raise RuntimeError('拾文隔离会话未准备')
spec=importlib.util.spec_from_file_location('shiwen_external_search',Path('D:/zcode1/douyin-discovery/discovery.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.PROFILE=PROFILE;m.prepare_profile=lambda:None
request=json.loads(Path(a.request).read_text(encoding='utf8'))
try:asyncio.run(m.run(request,Path(a.output)))
except Exception as exc:
    path=Path(a.output)
    previous=json.loads(path.read_text(encoding='utf8')) if path.exists() else {'items':[]}
    previous.update(status='error',error='话题组件未完成（'+type(exc).__name__+'）')
    m.atomic_write(path,previous)
