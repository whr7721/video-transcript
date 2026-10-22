"""Shared ASR and transcript persistence after a source adapter prepares media."""
import time
import media_buffer
from store import atomic_json


def finish_transcription(task, update, directory, audio, duration, metadata, start, media_available, cloud_key=""):
    update(duration=round(duration, 2), stage="transcribing", message="正在识别讲话，原文会逐段出现")
    from transcribe import local_transcribe, cloud_transcribe

    def progress(fraction, count, text):
        update(progress=round(fraction, 4), segment_count=count, partial_text=text,
               message=f"已识别 {count} 个语音片段")

    if task["provider"] == "cloud":
        result = cloud_transcribe(audio, directory / "cloud_chunks", progress, cloud_key)
    else:
        result = local_transcribe(audio, directory / "local_chunks", progress)
    result.update({**metadata, "duration": duration,
                   "total_seconds": round(time.perf_counter() - start, 2), "created_at": time.time(),
                   "cost_yuan": 0, "review_note": "原文由语音识别生成，保留讲话内容；人名、数字和专有名词建议回听核对。未进行全文人工校对。"})
    atomic_json(directory / "transcript.json", result)
    (directory / "transcript.txt").write_text(result["text"], encoding="utf-8")
    source_label = metadata.get('source_url') or metadata.get('source', {}).get('original_name') or '本地素材'
    markdown = f"# {metadata.get('title', '未命名素材')}\n\n作者：{metadata.get('author', '')}\n\n来源：{source_label}\n\n> {result['review_note']}\n\n## 讲话全文\n\n{result['text']}\n"
    (directory / "transcript.md").write_text(markdown, encoding="utf-8")
    media_buffer.state(task['id'], 'awaiting_review')
    update(status="completed", stage="completed", progress=1, partial_text="", completed_at=time.time(),
           result=result, media_available=media_available, elapsed_seconds=result["total_seconds"],
           message="全文已保存，音视频已进入缓冲，确认最终稿后才可清理")
