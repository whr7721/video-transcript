"""Customer data stays beside the installation, shared by Web and CLI."""
import os
from pathlib import Path

def configure():
    root=Path(__file__).resolve().parent
    data=root/'data-core'
    marker=data/'.core-profile'
    if data.exists() and any(data.iterdir()) and (not marker.exists() or marker.read_text()!='core-v1'):
        raise RuntimeError('数据目录不是本交付版目录，拒绝自动迁移')
    data.mkdir(exist_ok=True);marker.write_text('core-v1')
    os.environ['SHIWEN_CORE_DATA_DIR']=str(data)
    os.environ['SHIWEN_DATA_DIR']=str(data)
    os.environ['SHIWEN_PROFILE']='core'
    os.environ['SHIWEN_PUBLIC']='0'
