"""Source-independent media preparation. File admission is handled by the source adapter."""
import json
import subprocess

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
