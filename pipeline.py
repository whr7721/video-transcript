import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
import media_buffer

from session import prepare_session
from store import ROOT, atomic_json

MC_PY = Path(r"D:\zcode1\mediacrawler\.venv\Scripts\python.exe")


def input_url(text):
    urls = re.findall(r"https?://[^\s<>\"']+", text)
    if not urls:
        raise ValueError("请粘贴抖音分享链接，或包含链接的完整分享文本。")
    for url in urls:
        url = url.rstrip("，。；！）)]}")
        parsed = urlparse(url)
        if parsed.hostname in {"v.douyin.com", "www.douyin.com", "douyin.com", "iesdouyin.com", "www.iesdouyin.com"} and parsed.scheme == "https" and parsed.port in (None, 443) and not parsed.username and not parsed.password:
            return url
    raise ValueError("当前仅支持 HTTPS 抖音视频链接。")


def id_from_url(url):
    match = re.search(r"/(?:share/)?video/(\d{15,22})|[?&]modal_id=(\d{15,22})", url)
    return next((g for g in match.groups() if g), None) if match else None


def resolve_id(url):
    video_id = id_from_url(url)
    if video_id:
        return video_id
    with httpx.Client(trust_env=False, timeout=20, follow_redirects=False) as client:
        for _ in range(5):
            # Stop at the first redirect containing the ID. The landing page may
            # block a headless HTTP client even though the short URL works.
            response = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            location = response.headers.get("location")
            if location:
                from urllib.parse import urljoin
                url = input_url(urljoin(url, location))
                video_id = id_from_url(url)
                if video_id:
                    return video_id
            else:
                break
    raise RuntimeError("无法从分享链接取得作品编号，请尝试复制视频的完整链接。")


def get_metadata(video_id, job_dir):
    output = job_dir / "source.json"
    if output.exists():
        cached = json.loads(output.read_text(encoding="utf-8"))
        if cached.get("status") == "ok":
            return cached
    prepare_session()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        env.pop(key, None)
    try:
        completed = subprocess.run([str(MC_PY), "-B", "-X", "utf8", str(ROOT / "extractor.py"),
                                    "extract", "--id", video_id, "--output", str(output)],
                                   env=env, capture_output=True, timeout=130)
    except subprocess.TimeoutExpired:
        raise RuntimeError("获取视频超时，素材未丢失。请检查登录状态后重试。") from None
    if output.exists():
        result = json.loads(output.read_text(encoding="utf-8"))
        if result.get("status") == "ok":
            return result
        raise RuntimeError(result.get("error", "获取视频失败，请重新登录后重试。"))
    raise RuntimeError("采集组件未能启动，请检查 MediaCrawler 的现有 Python 环境。")


def media_host(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and parsed.port in (None, 443) and any(
        host == domain or host.endswith("." + domain)
        for domain in ["douyinvod.com", "douyin.com", "bytecdn.cn", "snssdk.com", "iesdouyin.com", "byteimg.com", "bytedance.com"])


def download_video(urls, target, progress):
    if target.exists() and target.stat().st_size > 1000:
        try:
            probe_media(target)
            return
        except Exception:
            pass
    partial = target.with_suffix(".part")
    for url in urls[:4]:
        if not media_host(url):
            continue
        try:
            with httpx.Client(trust_env=False, follow_redirects=False, timeout=httpx.Timeout(40, connect=15)) as client:
                for _ in range(5):
                    with client.stream("GET", url, headers={"Referer": "https://www.douyin.com/", "User-Agent": "Mozilla/5.0"}) as response:
                        if response.is_redirect:
                            from urllib.parse import urljoin
                            url = urljoin(url, response.headers["location"])
                            if not media_host(url):
                                raise RuntimeError("媒体跳转地址不在支持范围。")
                            continue
                        response.raise_for_status()
                        total = int(response.headers.get("content-length", 0))
                        if total > 1_000_000_000:
                            raise RuntimeError("单条视频超过首版 1GB 限制。")
                        media_buffer.ensure_space(total or 32_000_000)
                        size = 0
                        last = time.monotonic()
                        with partial.open("wb") as file:
                            for block in response.iter_bytes(256 * 1024):
                                media_buffer.ensure_space(len(block))
                                size += len(block)
                                if size > 1_000_000_000:
                                    raise RuntimeError("单条视频超过首版 1GB 限制。")
                                file.write(block)
                                if time.monotonic() - last > 0.7:
                                    progress(size, total)
                                    last = time.monotonic()
                        if size < 1000 or (total and size != total):
                            raise RuntimeError("视频下载不完整。")
                        probe_media(partial)
                        partial.replace(target)
                        return
                raise RuntimeError("视频下载跳转次数过多。")
        except media_buffer.BufferFull:
            raise
        except (httpx.HTTPError, ValueError, RuntimeError, subprocess.SubprocessError):
            partial.unlink(missing_ok=True)
    raise RuntimeError("视频下载失败或直链已过期，请重试以重新获取。")


def probe_media(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                            check=True, capture_output=True, timeout=35)
    info = json.loads(result.stdout)
    if not any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        raise RuntimeError("视频没有可识别的音轨。")
    duration = float(info.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise RuntimeError("无法读取视频时长。")
    return duration


def extract_audio(video, audio):
    if audio.exists():
        try:
            return probe_media(audio)
        except Exception:
            pass
    partial = audio.with_name("audio.partial.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(partial)], check=True, capture_output=True, timeout=180)
    duration = probe_media(partial)
    partial.replace(audio)
    return duration


def run_task(task, update, cloud_key=""):
    start = time.perf_counter()
    directory = ROOT / "data" / "jobs" / task["id"]
    directory.mkdir(parents=True, exist_ok=True)
    media_buffer.register(task['id'], pinned=task.get('keep_media', True))
    update(stage="resolving", status="running", message="正在识别分享链接", started_at=time.time(), error=None)
    video_id = task.get("video_id") or resolve_id(task["url"])
    update(video_id=video_id, stage="fetching", message="正在获取视频信息")
    metadata = get_metadata(video_id, directory)
    detail = metadata["detail"]
    title = detail.get("desc") or "未命名视频"
    author = detail.get("author", {}).get("nickname", "")
    if task.get("expected_sec_uid") and detail.get("author", {}).get("sec_uid") != task["expected_sec_uid"]:
        raise RuntimeError("作品作者不匹配，已停止该条处理。")
    update(title=title, author=author)
    video = directory / "original.mp4"
    update(stage="downloading", message="正在保存原视频")
    try:
        download_video(metadata["urls"], video, lambda size, total: update(downloaded_bytes=size, total_bytes=total))
    except media_buffer.BufferFull:
        raise
    except RuntimeError:
        # Refresh a CDN URL once; the production crawler remains untouched.
        (directory / "source.json").unlink(missing_ok=True)
        metadata = get_metadata(video_id, directory)
        download_video(metadata["urls"], video, lambda size, total: update(downloaded_bytes=size, total_bytes=total))
    update(stage="preparing", message="正在准备语音")
    duration = probe_media(video)
    if task.get("max_duration_sec") and duration > task["max_duration_sec"]:
        if not task.get("keep_media", True):
            video.unlink(missing_ok=True)
        update(status="skipped", stage="skipped", message=f"实际时长超过{task['max_duration_sec'] // 60}分钟，已跳过", duration=duration, media_available=video.exists())
        return
    if duration > 3600:
        raise RuntimeError("首版目前支持 1 小时以内内容；原视频已保留。")
    audio = directory / "audio.wav"
    reserve=int(duration*32000)+1_000_000
    if audio.exists():
        try:
            probe_media(audio)
            reserve=0
        except Exception:
            pass
    media_buffer.ensure_space(reserve)
    extract_audio(video, audio)
    update(duration=round(duration, 2), stage="transcribing", message="正在识别讲话，原文会逐段出现")
    from transcribe import local_transcribe, cloud_transcribe

    def progress(fraction, count, text):
        update(progress=round(fraction, 4), segment_count=count, partial_text=text,
               message=f"已识别 {count} 个语音片段")

    if task["provider"] == "cloud":
        result = cloud_transcribe(audio, directory / "cloud_chunks", progress, cloud_key)
    else:
        result = local_transcribe(audio, directory / "local_chunks", progress)
    result.update({"video_id": video_id, "title": title, "author": author,
                   "source_url": f"https://www.douyin.com/video/{video_id}", "duration": duration,
                   "total_seconds": round(time.perf_counter() - start, 2), "created_at": time.time(),
                   "cost_yuan": 0, "review_note": "原文由语音识别生成，保留讲话内容；人名、数字和专有名词建议回听核对。未进行全文人工校对。"})
    atomic_json(directory / "transcript.json", result)
    (directory / "transcript.txt").write_text(result["text"], encoding="utf-8")
    markdown = f"# {title}\n\n作者：{author}\n\n来源：{result['source_url']}\n\n> {result['review_note']}\n\n## 讲话全文\n\n{result['text']}\n"
    (directory / "transcript.md").write_text(markdown, encoding="utf-8")
    media_buffer.state(task['id'], 'awaiting_review')
    update(status="completed", stage="completed", progress=1, partial_text="", completed_at=time.time(),
           result=result, media_available=video.exists(), elapsed_seconds=result["total_seconds"],
           message="全文已保存，音视频已进入缓冲，确认最终稿后才可清理")
