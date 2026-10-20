"""Download pinned official model assets to this project, using proxy only here."""
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELS = ROOT / "models"
NAME = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"


def download(name):
    path = MODELS / name
    if path.exists() and path.stat().st_size > 1000:
        return path
    partial = path.with_suffix(path.suffix + ".partial")
    command = ["curl.exe", "--fail", "--location", "--retry", "3", "--connect-timeout", "20",
               "--max-time", "1200", "--ssl-revoke-best-effort", "--proxy", "http://127.0.0.1:7890",
               BASE + name, "--output", str(partial)]
    subprocess.run(command, check=True)
    partial.replace(path)
    return path


def main():
    MODELS.mkdir(exist_ok=True)
    if not (MODELS / NAME / "model.int8.onnx").exists():
        archive = download(NAME + ".tar.bz2")
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                target = (MODELS / member.name).resolve()
                if not target.is_relative_to(MODELS.resolve()) or member.issym() or member.islnk():
                    raise RuntimeError("模型压缩包路径校验失败")
            bundle.extractall(MODELS, filter="data")
    download("silero_vad.onnx")
    files = [MODELS / NAME / "model.int8.onnx", MODELS / NAME / "tokens.txt", MODELS / "silero_vad.onnx"]
    manifest = {str(p.relative_to(MODELS)): {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
    (MODELS / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("官方模型下载完成，文件指纹已记录。")


if __name__ == "__main__":
    main()
