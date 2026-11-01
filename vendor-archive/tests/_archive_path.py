"""Archive-only import path: vendor-archive 里的脚本与仓库根目录都要能 import。"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = Path(__file__).resolve().parents[1]
for path in (str(ROOT), str(ARCHIVE)):
    if path not in sys.path:
        sys.path.insert(0, path)
