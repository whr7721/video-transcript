"""Package-local paths; no inherited production session/data directories."""
import os,sys
from pathlib import Path
def configure():
 root=Path(__file__).resolve().parent
 data=Path(os.environ.get('SHIWEN_FULL_DATA_DIR',root/'data-full')).resolve()
 os.environ.update(SHIWEN_DATA_DIR=str(data),SHIWEN_PROFILE='full',SHIWEN_PUBLIC='0',SHIWEN_MC_PYTHON=sys.executable,SHIWEN_MEDIACRAWLER_DIR=str(root/'vendor/mediacrawler'),SHIWEN_DISCOVERY_ADAPTER=str(root/'vendor/douyin_discovery.py'),SHIWEN_DISCOVERY_PROFILE=str(data/'browser'),SHIWEN_DOUYIN_PROFILE=os.environ.get('SHIWEN_FULL_DOUYIN_PROFILE',str(data/'source-profile')),SHIWEN_OCR_PYTHON=sys.executable,PLAYWRIGHT_BROWSERS_PATH=str(root/'.runtime/browsers'))
 os.environ['PATH']=str(root/'.runtime/bin')+os.pathsep+str(root/'.venv/Lib/site-packages/playwright/driver')+os.pathsep+os.environ.get('PATH','')
