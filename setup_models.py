"""Prepare pinned official CPU models; standard library, no implicit proxy."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = 'sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17'
BASE = 'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/'
# Official release API digests, queried before downloading on 2026-10-22.
ASSETS = {
    NAME+'.tar.bz2': (163002883, '7d1efa2138a65b0b488df37f8b89e3d91a60676e416f515b952358d83dfd347e'),
    'silero_vad.onnx': (643854, '9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6'),
}
FILES = {
    NAME+'/model.int8.onnx': (239233841, 'c71f0ce00bec95b07744e116345e33d8cbbe08cef896382cf907bf4b51a2cd51'),
    NAME+'/tokens.txt': (315894, 'f449eb28dc567533d7fa59be34e2abca8784f771850c78a47fb731a31429a1dc'),
    'silero_vad.onnx': ASSETS['silero_vad.onnx'],
}


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def valid(path, expected):
    path = Path(path)
    return path.is_file() and not path.is_symlink() and path.stat().st_size == expected[0] and fingerprint(path) == expected[1]


def verify(directory):
    return {name: valid(Path(directory)/name, expected) for name, expected in FILES.items()}


def download(name, destination, opener):
    expected = ASSETS[name]
    started, received = time.monotonic(), 0
    request = urllib.request.Request(BASE+name, headers={'User-Agent': 'Shiwen-model-setup/1'})
    try:
        with opener.open(request, timeout=30) as response, destination.open('wb') as output:
            if response.status != 200 or not response.url.startswith('https://'):
                raise RuntimeError('模型服务未返回 HTTPS 完整文件')
            while True:
                if time.monotonic()-started > 1800:
                    raise TimeoutError('模型下载超过30分钟')
                block = response.read(1024*1024)
                if not block:
                    break
                received += len(block)
                if received > expected[0]:
                    raise ValueError('模型下载超过固定大小')
                output.write(block)
        if not valid(destination, expected):
            raise ValueError('模型大小或 SHA256 与官方固定版本不符')
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return {'asset': name, 'bytes': received, 'sha256': expected[1], 'seconds': round(time.monotonic()-started, 3)}


def extract_verified(archive, target):
    """Read only two pinned regular members, never extract arbitrary archive paths."""
    required = {name for name in FILES if name.startswith(NAME+'/')}
    found = set()
    with tarfile.open(archive, 'r:bz2') as bundle:
        for member in bundle:
            if member.name not in required:
                continue
            if member.name in found or not member.isfile() or member.size != FILES[member.name][0]:
                raise ValueError('模型压缩包成员不符合固定清单')
            path = target/member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as source, path.open('wb') as output:
                shutil.copyfileobj(source, output, 1024*1024)
            if not valid(path, FILES[member.name]):
                raise ValueError('模型成员校验失败')
            found.add(member.name)
    if found != required:
        raise ValueError('模型压缩包缺少文件')


def prepare(directory, proxy=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    initial = verify(directory)
    report = {'schema_version': 1, 'system': platform.system(), 'release': platform.release(),
              'python': platform.python_version(), 'proxy_mode': 'explicit' if proxy else 'direct',
              'proxy_environment_present': any(os.environ.get(k) for k in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy')),
              'downloads': [], 'already_verified': initial}
    # Empty mapping disables both environment and Windows registry proxy discovery.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': proxy, 'http': proxy} if proxy else {}))
    if not all(initial.values()):
        if shutil.disk_usage(directory).free < 600_000_000:
            raise RuntimeError('模型准备需要至少600MB临时可用空间')
        with tempfile.TemporaryDirectory(prefix='.model-setup-', dir=directory) as temporary:
            stage = Path(temporary)
            if not all(initial[name] for name in FILES if name.startswith(NAME+'/')):
                archive = stage/(NAME+'.tar.bz2')
                report['downloads'].append(download(archive.name, archive, opener))
                extract_verified(archive, stage)
                for name in FILES:
                    if name.startswith(NAME+'/'):
                        final = directory/name
                        final.parent.mkdir(parents=True, exist_ok=True)
                        (stage/name).replace(final)
            if not initial['silero_vad.onnx']:
                vad = stage/'silero_vad.onnx'
                report['downloads'].append(download(vad.name, vad, opener))
                vad.replace(directory/vad.name)
    report['verified'] = verify(directory)
    if not all(report['verified'].values()):
        raise RuntimeError('安装后的模型校验失败')
    return report


def main():
    parser = argparse.ArgumentParser(description='准备固定 CPU 模型；默认直连，不读取系统代理')
    parser.add_argument('--models-dir', type=Path, default=ROOT/'models')
    parser.add_argument('--proxy', help='可选 http(s) 代理；不会记录地址或凭据')
    parser.add_argument('--verify-only', action='store_true', help='仅离线校验，不联网')
    parser.add_argument('--report', type=Path, help='保存不含凭据的 JSON 记录')
    args = parser.parse_args()
    if args.proxy and not args.proxy.startswith(('http://','https://')):
        parser.error('代理必须是 http(s) 地址')
    try:
        report = {'verified': verify(args.models_dir)} if args.verify_only else prepare(args.models_dir, args.proxy)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if all(report['verified'].values()) else 1
    except Exception as exc:
        # Network exception strings may contain a credential-bearing explicit proxy URL.
        print(f'模型准备失败（{type(exc).__name__}）。请检查网络/磁盘，重试或按 README 离线准备。未通过校验的文件不会安装。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
