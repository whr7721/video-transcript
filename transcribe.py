import hashlib
import json
import re
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "models" / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17"
MODEL_VERSION = "sensevoice-int8-20240717-vad-v1"
_recognizer = None


def get_recognizer(language="zh"):
    global _recognizer
    if language not in {"auto","zh","en","ja","ko","yue"}:
        raise ValueError("不支持的识别语言")
    if _recognizer is None or getattr(get_recognizer, "language", None) != language:
        if not (MODEL / "model.int8.onnx").exists():
            raise RuntimeError("本地模型未就绪，请按当前版本 README 准备模型文件。")
        import sherpa_onnx
        _recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(MODEL / "model.int8.onnx"), tokens=str(MODEL / "tokens.txt"),
            num_threads=4, use_itn=True, language=language, provider="cpu", debug=False,
        )
        get_recognizer.language = language
    return _recognizer


def clean_text(text):
    text = re.sub(r"<\|unk\|>|<unk>|\[UNK\]", "〔听辨不清〕", text, flags=re.IGNORECASE)
    text = re.sub(r"<\|[^|]*\|>", "", text).strip()
    return text


def paragraphs(segments):
    blocks, current = [], ""
    last_end = 0
    for segment in segments:
        text = segment["text"].strip()
        if not text:
            continue
        if current and (len(current) >= 140 or segment["start"] - last_end >= 2.5):
            blocks.append(current)
            current = ""
        if current and not re.search(r"[。！？.!?，,；;：:]$", current):
            current += "，" if re.search(r"[\u4e00-\u9fff]", text) else " "
        current += text
        last_end = segment["end"]
    if current:
        blocks.append(current)
    return "\n\n".join(blocks)


def local_transcribe(audio, cache_dir, progress, language="zh"):
    import sherpa_onnx
    recognizer = get_recognizer() if language == 'zh' else get_recognizer(language)
    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = str(ROOT / "models" / "silero_vad.onnx")
    config.silero_vad.threshold = 0.35
    config.silero_vad.min_silence_duration = 0.45
    config.silero_vad.min_speech_duration = 0.15
    config.silero_vad.max_speech_duration = 20
    config.sample_rate = 16000
    config.num_threads = 1
    vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=60)
    window = config.silero_vad.window_size
    cache_dir.mkdir(exist_ok=True)
    segments = []
    reused = 0
    started = time.perf_counter()
    with wave.open(str(audio), "rb") as reader:
        if (reader.getframerate(), reader.getnchannels(), reader.getsampwidth()) != (16000, 1, 2):
            raise RuntimeError("音频预处理格式不正确。")
        frames = reader.getnframes()
        processed = 0

        def drain():
            nonlocal reused
            while not vad.empty():
                speech = vad.front
                start = int(speech.start)
                samples = np.array(speech.samples, dtype=np.float32)
                end = start + len(samples)
                fingerprint = hashlib.sha256(samples.tobytes() + MODEL_VERSION.encode() + (language.encode() if language != 'zh' else b'')).hexdigest()[:16]
                cache = cache_dir / f"{start}-{end}-{fingerprint}.json"
                if cache.exists():
                    segment = json.loads(cache.read_text(encoding="utf-8"))
                    reused += 1
                else:
                    stream = recognizer.create_stream()
                    stream.accept_waveform(16000, samples)
                    recognizer.decode_stream(stream)
                    segment = {"start": round(start / 16000, 3), "end": round(end / 16000, 3),
                               "text": clean_text(stream.result.text), "timing_source": "vad_segment"}
                    from store import atomic_json
                    atomic_json(cache, segment)
                segments.append(segment)
                vad.pop()
                progress(min(processed / frames, 1), len(segments), paragraphs(segments))

        while True:
            data = reader.readframes(window)
            if not data:
                break
            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            processed += len(samples)
            vad.accept_waveform(samples)
            drain()
        vad.flush()
        drain()
    text = paragraphs(segments)
    if len(text.strip()) < 2:
        raise RuntimeError("未识别到可用讲话内容，请检查原视频是否有语音。")
    return {"text": text, "segments": segments, "engine": "SenseVoice INT8 · 本地 CPU",
            "model_version": MODEL_VERSION, "asr_seconds": round(time.perf_counter() - started, 2),
            "segments_reused": reused, "timing_precision": "语音段边界，非精准词级字幕"}


def cloud_transcribe(audio, cache_dir, progress, key):
    import subprocess
    import httpx
    from store import atomic_json
    if not key:
        raise RuntimeError("请先在设置中填写硅基流动 Key，或改用本地识别。")
    cache_dir.mkdir(exist_ok=True)
    with wave.open(str(audio), "rb") as reader:
        duration = reader.getnframes() / reader.getframerate()
    segments = []
    started = time.perf_counter()
    count = max(1, int(np.ceil(duration / 180)))
    for index in range(count):
        start, end = index * 180, min((index + 1) * 180, duration)
        cache = cache_dir / f"cloud-{index}.json"
        if cache.exists():
            segment = json.loads(cache.read_text(encoding="utf-8"))
        else:
            part = cache_dir / f"cloud-{index}.mp3"
            import media_buffer
            media_buffer.ensure_space(2_000_000)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(end-start),
                            "-i", str(audio), "-b:a", "64k", str(part)], check=True, capture_output=True, timeout=90)
            error = None
            for attempt in range(3):
                try:
                    with httpx.Client(trust_env=False, timeout=httpx.Timeout(120, connect=15)) as client, part.open("rb") as file:
                        response = client.post("https://api.siliconflow.cn/v1/audio/transcriptions",
                                               headers={"Authorization": f"Bearer {key}"},
                                               files={"file": (part.name, file, "audio/mpeg")},
                                               data={"model": "FunAudioLLM/SenseVoiceSmall"})
                    if response.status_code in (401, 403):
                        raise RuntimeError("识别服务拒绝访问，请检查 Key 与模型权限。")
                    if response.status_code == 429 or response.status_code >= 500:
                        raise httpx.TransportError("服务暂时繁忙")
                    response.raise_for_status()
                    text = clean_text(response.json().get("text", ""))
                    if not text:
                        raise RuntimeError("识别服务没有返回文字。")
                    segment = {"start": start, "end": end, "text": text, "timing_source": "upload_chunk"}
                    atomic_json(cache, segment)
                    error = None
                    break
                except (httpx.HTTPError, ValueError):
                    error = RuntimeError("云端识别暂时失败，已保留素材，可稍后重试。")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
            if error:
                raise error
            part.unlink(missing_ok=True)
        segments.append(segment)
        progress((index + 1) / count, index + 1, paragraphs(segments))
    return {"text": paragraphs(segments), "segments": segments, "engine": "SenseVoice · 硅基流动",
            "model_version": "FunAudioLLM/SenseVoiceSmall", "asr_seconds": round(time.perf_counter() - started, 2),
            "timing_precision": "上传片段边界，不提供精准字幕"}
