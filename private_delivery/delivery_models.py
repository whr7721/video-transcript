"""Install only the exact ONNX files accepted by the existing model verifier."""
import argparse
import shutil
from pathlib import Path
import httpx
import setup_models


def prepare(local=None,offline=False):
    target=Path(__file__).resolve().parent/'models';target.mkdir(exist_ok=True)
    repo='https://hf-mirror.com/csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17/resolve/main/'
    for name,expected in setup_models.FILES.items():
        dest=target/name
        if setup_models.valid(dest,expected):continue
        if local:
            source=Path(local)/name
            if not setup_models.valid(source,expected):raise RuntimeError('本地模型缺失或校验失败：'+name)
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest);continue
        if offline:raise RuntimeError('离线模型缺失：'+name)
        url=setup_models.BASE+name if name=='silero_vad.onnx' else repo+Path(name).name
        dest.parent.mkdir(parents=True,exist_ok=True);part=dest.with_suffix('.part')
        with httpx.Client(follow_redirects=True,timeout=60) as c:
            with c.stream('GET',url) as r:
                r.raise_for_status();size=0
                with part.open('wb') as f:
                    for block in r.iter_bytes(1024*1024):
                        size+=len(block)
                        if size>expected[0]:raise RuntimeError('模型下载超过预期大小')
                        f.write(block)
        if not setup_models.valid(part,expected):raise RuntimeError('镜像模型校验失败：'+name)
        part.replace(dest)
    # The small VAD is pinned to the official upstream export; no replacement model.
    if not all(setup_models.verify(target).values()):raise RuntimeError('模型校验失败')
    if (Path(__file__).parent/'full-package.json').exists():
        import setup_speakers
        setup_speakers.prepare(target,local,offline)
    print('Models verified: SenseVoice INT8 and Silero VAD.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--model-dir');p.add_argument('--offline',action='store_true');a=p.parse_args()
    try:prepare(a.model_dir,a.offline)
    except Exception as exc:
        print('模型准备失败：'+str(exc)+'。可重试，或用 -ModelDir 指定已校验的模型目录。')
        raise SystemExit(1)
