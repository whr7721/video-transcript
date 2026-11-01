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

MC_PY = Path(os.environ.get("SHIWEN_MC_PYTHON", r"D:\zcode1\mediacrawler\.venv\Scripts\python.exe"))


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
    match = re.search(r"/(?:share/)?(?:video|note)/(\d{15,22})(?=[/?#]|$)|[?&]modal_id=(\d{15,22})(?=[&#]|$)", url)
    return next((g for g in match.groups() if g), None) if match else None


def kind_from_url(url):
    """图文作品（note）与视频共用作品编号空间，只能从路径判断。"""
    return "note" if re.search(r"/(?:share/)?note/\d{15,22}", url) else "video"


def resolve(url):
    """返回 (作品编号, 作品类型)；短链逐跳展开，类型取最后一跳。"""
    video_id = id_from_url(url)
    if video_id:
        return video_id, kind_from_url(url)
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
                    return video_id, kind_from_url(url)
            else:
                break
    raise RuntimeError("无法从分享链接取得作品编号，请尝试复制视频或图文的完整链接。")


def resolve_id(url):
    return resolve(url)[0]


def get_metadata(video_id, job_dir):
    from douyin_session_guard import session_guard
    with session_guard():return _get_metadata(video_id,job_dir)

def _get_metadata(video_id, job_dir):
    output = job_dir / "source.json"
    if output.exists():
        cached = json.loads(output.read_text(encoding="utf-8"))
        if cached.get("status") == "ok":
            return cached
    prepare_session()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "SHIWEN_SESSION_LOCK_HELD":"1"}
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
        for domain in ["douyinvod.com", "douyin.com", "douyinpic.com", "bytecdn.cn", "snssdk.com", "iesdouyin.com", "byteimg.com", "bytedance.com"])


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


from media_io import probe_media, extract_audio


def note_payload(post_id, directory=None):
    """图集作品详情（images 列表）。同一作品共用缓存，避免重复开浏览器会话。

    只有 run_task 内部（已持有抖音会话互斥）才把 SHIWEN_SESSION_LOCK_HELD 传给子进程；
    private_images.metadata 自己不开锁，所以不复用本函数，避免双重加锁判断出错。
    """
    if directory is None:
        from store import DATA
        directory = DATA / "image-sources" / post_id
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / "source.json"
    if output.exists():
        cached = json.loads(output.read_text(encoding="utf-8"))
        if cached.get("status") == "ok" and cached.get("id") == post_id:
            return cached
    prepare_session()
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1", "SHIWEN_SESSION_LOCK_HELD":"1"}
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        env.pop(key, None)
    try:
        subprocess.run([str(MC_PY), "-B", "-X", "utf8", str(ROOT / "extractor.py"),
                        "images", "--id", post_id, "--output", str(output)],
                       env=env, capture_output=True, timeout=130,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        raise RuntimeError("获取图文超时，素材未丢失。请检查登录状态后重试。") from None
    if not output.exists():
        raise RuntimeError("采集组件未能启动，请检查 MediaCrawler 的现有 Python 环境。")
    result = json.loads(output.read_text(encoding="utf-8"))
    if result.get("status") == "ok" and result.get("id") == post_id:
        return result
    raise RuntimeError(result.get("error") or "获取图文失败，请重新登录后重试。")


def run_task(task, update, cloud_key=""):
    from douyin_session_guard import session_guard
    with session_guard():return _run_task(task,update,cloud_key)

def _run_task(task, update, cloud_key=""):
    start = time.perf_counter()
    from store import DATA
    directory = DATA / "jobs" / task["id"]
    directory.mkdir(parents=True, exist_ok=True)
    media_buffer.register(task['id'], pinned=task.get('keep_media', True))
    update(stage="resolving", status="running", message="正在识别分享链接", started_at=time.time(), error=None)
    if task.get("video_id"):
        video_id = task["video_id"]
        media_kind = task.get("media_kind") or kind_from_url(task.get("url", ""))
    else:
        video_id, media_kind = resolve(task["url"])
    if media_kind == "note":
        update(video_id=video_id, media_kind="note", stage="fetching", message="正在获取图文作品信息")
        return _run_note(task, update, directory, video_id, start)
    update(video_id=video_id, media_kind="video", stage="fetching", message="正在获取视频信息")
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
    if duration > 10800:
        raise RuntimeError("目前支持 3 小时以内内容；原视频已保留。")
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
    from transcript_stage import finish_transcription
    finish_transcription(task, update, directory, audio, duration,
                         {"video_id": video_id, "title": title, "author": author,
                          "source_url": f"https://www.douyin.com/video/{video_id}"},
                         start, video.exists(), cloud_key)


def _run_note(task, update, directory, note_id, start):
    """抖音图文：图集原图 → 本地OCR → 文字稿，产物结构与小红书图文一致。"""
    import image_documents
    payload = note_payload(note_id)
    title = (payload.get("title") or "未命名图文").strip()
    author = payload.get("author") or ""
    if task.get("expected_sec_uid"):
        raise RuntimeError("图文不支持按博主批次校验，请单独提交该作品。")
    update(title=title, author=author)
    detail = {"desc": title, "author": {"nickname": author, "sec_uid": payload.get("sec_uid") or ""},
              "create_time": payload.get("create_time"),
              "text_extra": [{"hashtag_name": tag} for tag in payload.get("tags") or []]}
    atomic_json(directory / "source.json", {"status": "ok", "id": note_id, "detail": detail})
    images = payload.get("images") or []
    if not images:
        raise RuntimeError("该作品没有可用的图文图片，未生成文字稿。")
    urls = [[url for url in (image.get("urls") or []) if isinstance(url, str)][:3] for image in images]
    update(stage="downloading", message="正在保存图文原图")
    text, blocks, article_id = image_documents.to_document(
        title, urls, source_url=f"https://www.douyin.com/note/{note_id}",
        checkpoint=directory / "note-article.json", referer="https://www.douyin.com/",
        author=author, description=title, progress=update)
    result = {"text": text, "segments": [{"text": block["text"]} for block in blocks],
              "images": len(images), "article_id": article_id,
              "engine": "image_ocr", "timing_precision": "none",
              "video_id": note_id, "title": title, "author": author,
              "source_url": f"https://www.douyin.com/note/{note_id}", "duration": None,
              "total_seconds": round(time.perf_counter() - start, 2), "created_at": time.time(),
              "cost_yuan": 0,
              "review_note": "文字由本地OCR从图文原图识别，可能漏字、错序；人名、数字和专有名词建议对照原图核对。未进行全文人工校对。"}
    atomic_json(directory / "transcript.json", result)
    (directory / "transcript.txt").write_text(text, encoding="utf-8")
    markdown = f"# {title}\n\n作者：{author}\n\n来源：{result['source_url']}\n\n> {result['review_note']}\n\n## 图文文字稿（{len(images)} 张）\n\n{text}\n"
    (directory / "transcript.md").write_text(markdown, encoding="utf-8")
    update(status="completed", stage="completed", progress=1, partial_text="", completed_at=time.time(),
           result=result, media_available=False, elapsed_seconds=result["total_seconds"],
           message="图文文字稿已保存；原图与识别区域在图文素材库中可对照核对")
