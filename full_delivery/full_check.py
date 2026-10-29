import full_env
full_env.configure()
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
import setup_models,ocr_worker,rapidocr
root=Path(__file__).resolve().parent
assert Path(sys.base_prefix).resolve().is_relative_to(root),'Python must be package-local'
assert all(setup_models.verify(root/'models').values())
for n,h in ocr_worker.MODEL_HASHES.items():assert hashlib.sha256((Path(rapidocr.__file__).parent/'models'/n).read_bytes()).hexdigest()==h
import app,link_ingest
link_ingest.configure(True)
assert 'douyin' in link_ingest.INGESTERS and 'bilibili' in link_ingest.PRECHECKS
for name in ['ffmpeg','ffprobe','deno','node']:assert shutil.which(name) and Path(shutil.which(name)).resolve().is_relative_to(root)
code="import os,sys;os.chdir(os.environ['SHIWEN_MEDIACRAWLER_DIR']);sys.path.insert(0,os.getcwd());from media_platform.douyin.client import DouYinClient;print('collector import ready')"
subprocess.run([sys.executable,'-B','-c',code],check=True,timeout=30)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True);page=browser.new_page();page.set_content('<title>Shiwen offline browser check</title>');assert page.title()=='Shiwen offline browser check';browser.close()
report={'profile':'full','package_local_python':True,'models':True,'ocr_models':True,'chromium_launch':True,'collector_import':True,'platforms':['youtube','bilibili','douyin','rss']}
(root/'.runtime/check.json').write_text(json.dumps(report,indent=2),encoding='utf8');print('Full Shiwen ready; package-local tools/models/browser verified.')
