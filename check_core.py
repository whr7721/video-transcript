"""Readiness checks without importing the app or touching its database."""
import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
import setup_models

ROOT = Path(__file__).resolve().parent


def check(port=8766, require_models=False):
    results = []
    def add(name, ok, detail, required=True):
        results.append({'name': name, 'ok': bool(ok), 'required': required, 'detail': detail})
    add('python', sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8,
        '需要 Python 3.11 x64；当前 '+platform.python_version())
    add('windows', platform.system() == 'Windows', '目标平台 Windows 10/11')
    for line in (ROOT/'requirements.lock.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, wanted = line.strip().split('==')
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = '未安装'
        add('dependency:'+name, installed == wanted, f'需要 {wanted}，当前 {installed}；请按 README 安装锁定依赖')
    for name in ('ffmpeg','ffprobe'):
        executable = shutil.which(name)
        try:
            result = subprocess.run([executable,'-version'], capture_output=True, timeout=10) if executable else None
            ok = result is not None and result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        add(name, ok, '已在 PATH 可运行' if ok else '请安装 FFmpeg 并将 bin 加入 PATH，重新打开 PowerShell')
    data = Path(os.environ.get('SHIWEN_CORE_DATA_DIR', ROOT/'data-core')).resolve()
    marker = data/'.core-profile'
    safe = data != (ROOT/'data').resolve()
    if data.exists():
        if not data.is_dir():
            safe = False
        elif any(data.iterdir()):
            try:
                safe = safe and marker.is_file() and marker.read_text(encoding='utf-8') == 'core-v1'
            except (OSError, UnicodeError):
                safe = False
    add('data-profile', safe, '必须为空目录或已标记的核心数据目录；不会自动迁移')
    ancestor = data
    while not ancestor.is_dir():
        ancestor = ancestor.parent
    try:
        with tempfile.TemporaryFile(dir=ancestor) as probe:
            probe.write(b'write-check')
        writable = True
    except OSError:
        writable = False
    add('data-writable', writable, '数据目录或其现有父目录须可写')
    free = shutil.disk_usage(ancestor).free
    add('disk', free >= 1_000_000_000, f'当前可用 {free//1_000_000}MB；建议至少6GB以容纳5GB缓冲及模型')
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1',port))
            available = True
        except OSError:
            available = False
    add('port', available, f'{port} '+('可用' if available else '已占用；停止同一核心实例或使用 -Port 指定空闲端口'))
    add('frontend', (ROOT/'frontend/dist-core/index.html').is_file(), '需随包预编译工作台，无需 Node')
    model_files = setup_models.verify(ROOT/'models')
    has_model_files = any((ROOT/'models'/name).exists() for name in model_files)
    for name, ok in model_files.items():
        add('model:'+name, ok, '固定 SHA256 校验；缺失/损坏时运行 setup_models.py', require_models or has_model_files)
    return {'ready': all(r['ok'] for r in results if r['required']), 'checks': results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766, choices=range(1024,65536), metavar='1024..65535')
    parser.add_argument('--require-models', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        report = check(args.port,args.require_models)
    except (OSError, ValueError) as exc:
        print(f'FAIL 环境检查无法完成（{type(exc).__name__}）；检查目录权限与锁文件完整性，按 README 重新解压到可写目录。')
        return 1
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for item in report['checks']:
        print(('OK' if item['ok'] else 'FAIL' if item['required'] else 'OPTIONAL')+' '+item['name']+': '+item['detail'])
    return 0 if report['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
