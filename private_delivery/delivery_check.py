import customer_env
customer_env.configure()
import json
import shutil
import sys
from pathlib import Path
import app_core
import cli_summary
import setup_models
root=Path(__file__).resolve().parent
assert Path(sys.base_prefix).resolve().is_relative_to(root)
assert all(setup_models.verify(root/'models').values())
tools={name:shutil.which(name) for name in ('ffmpeg','ffprobe','deno')}
assert all(p and Path(p).resolve().is_relative_to(root) for p in tools.values())
report=dict(python=sys.executable,base_prefix=sys.base_prefix,tools=tools,model_verified=True)
(root/'.runtime/check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('Shiwen ready: package-local Python, media tools and models verified.')
