import argparse
import hashlib
import json
import time

import settings
import store
from pipeline import input_url, run_task


def main():
    parser = argparse.ArgumentParser(description="抖音链接 → 忠实讲话全文")
    parser.add_argument("share_text")
    parser.add_argument("--provider", choices=["local", "cloud"], default="local")
    args = parser.parse_args()
    store.init()
    url = input_url(args.share_text)
    task_id = hashlib.sha256((url + "|" + args.provider).encode()).hexdigest()[:16]
    task = store.get(task_id) or {"id": task_id, "url": url, "provider": args.provider,
                                "created_at": time.time(), "status": "queued", "stage": "queued"}
    if task.get("status") == "completed":
        print(f"已完成：data/jobs/{task_id}/transcript.txt")
        return
    store.save(task)

    def update(**fields):
        task.update(fields)
        store.save(task)
        print(json.dumps({k: v for k, v in fields.items() if k not in {"partial_text", "result"}}, ensure_ascii=False), flush=True)

    try:
        run_task(task, update, settings.cloud_key() if args.provider == "cloud" else "")
    except Exception as exc:
        update(status="failed", error=str(exc))
        raise
    print(f"文稿：{store.ROOT / 'data' / 'jobs' / task_id / 'transcript.txt'}")


if __name__ == "__main__":
    main()
