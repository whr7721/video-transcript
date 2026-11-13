"""自用入口：链接 → 转写稿 → 事实卡片。一条命令，不启动服务、不碰前端、不调用模型。

    python grab.py "https://www.xiaoyuzhoufm.com/episode/xxxx"
    python grab.py "https://www.bilibili.com/video/BVxxxx" --top 30

支撑：抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。
转写在本机完成（SenseVoice INT8，约 30 倍实时，零费用）；事实抽取是纯规则，不计配额。

刻意不做的事：不做摘要、不写二创、不切片、不做导图 —— 这些交给 agent，不再固化进工具。
"""
import argparse
import contextlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import facts  # noqa: E402


def grab(url, language="auto", episode=None, top=40):
    import link_ingest

    args = argparse.Namespace(url=url, language=language, episode=episode,
                              diarize=False, speakers=0, summarize=False)
    link_ingest.configure(True)  # 私有平台（抖音/小红书）需要；公开平台不受影响

    def progress(**fields):
        stage = fields.get("stage")
        if stage in {"cached", "transcribing", "downloading", "subtitles", "resolving", "diarizing"}:
            extra = ""
            if fields.get("progress") is not None:
                extra = f" {fields['progress'] * 100:.0f}%"
            elif fields.get("segment_count"):
                extra = f" {fields['segment_count']} 段"
            print(f"\r[{stage}]{extra}", end="", file=sys.stderr, flush=True)

    with contextlib.redirect_stdout(sys.stderr):
        ident = link_ingest.add(args, progress=progress)
    print("", file=sys.stderr)
    if not ident:
        raise SystemExit("未完成：RSS 需要先用 --episode 指定集数。")
    return ident


def main(argv=None):
    parser = argparse.ArgumentParser(description="链接 → 转写 + 事实卡片（自用）")
    parser.add_argument("url", help="视频/播客链接，或本地音视频路径")
    parser.add_argument("--top", type=int, default=40, help="输出多少条事实卡片")
    parser.add_argument("--lang", default="auto", choices=["auto", "zh", "en", "ja", "ko", "yue"])
    parser.add_argument("--episode", type=int, help="RSS / 播客：第几集")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args(argv)

    ident = grab(args.url, args.lang, args.episode, args.top)

    import store
    directory = Path(store.DATA) / "jobs" / ident
    data = json.loads((directory / "transcript.json").read_text(encoding="utf-8"))
    rows = facts.build(data.get("segments") or [], args.top)

    if args.json:
        print(json.dumps({"job": ident, "dir": str(directory),
                          "title": data.get("title"), "count": len(rows), "facts": rows},
                         ensure_ascii=False, indent=2))
        return

    strong = [r for r in rows if r["score"] >= 8]
    (directory / "facts.md").write_text(facts.render(ident, data, rows), encoding="utf-8")
    print(f"\n{data.get('title') or '未命名'}")
    print(f"{facts.stamp(data.get('duration') or 0)} ｜ {len(data.get('text') or '')} 字 ｜ "
          f"强候选 {len(strong)} 条 / 共 {len(rows)} 条 ｜ {directory}\n")
    for i, row in enumerate(rows, 1):
        mark = "★" if row["score"] >= 8 else " "
        print(f"{mark}{i:>2} {facts.stamp(row['t'])}  {row['text']}")
    print(f"\n全文：{directory / 'transcript.txt'}\n事实表：{directory / 'facts.md'}")


if __name__ == "__main__":
    main()
