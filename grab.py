"""自用入口：链接 → 转写稿。一条命令，不启动服务、不碰前端、不调用模型。

    python grab.py "https://www.xiaoyuzhoufm.com/episode/xxxx"
    python grab.py "https://www.bilibili.com/video/BVxxxx" --facts

转完打印：标题、时长、字数、文字长什么样、转写稿在哪、视频在哪。
剩下的事（摘要、二创、判断值不值得做、要不要抽帧看画面）读文字和视频之后自己决定。

转写在本机完成（SenseVoice INT8，约 30 倍实时，零费用）。
"""
import argparse
import contextlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import facts  # noqa: E402


def grab(url, language="auto", episode=None):
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
    parser = argparse.ArgumentParser(description="链接 → 转写 + 概览（自用）")
    parser.add_argument("url", help="视频/播客链接，或本地音视频路径")
    parser.add_argument("--facts", action="store_true", help="顺带生成事实卡 facts.md")
    parser.add_argument("--steps", action="store_true", help="顺带生成操作流 steps.md")
    parser.add_argument("--top", type=int, default=40, help="事实卡条数，默认 40")
    parser.add_argument("--lang", default="auto", choices=["auto", "zh", "en", "ja", "ko", "yue"])
    parser.add_argument("--episode", type=int, help="RSS / 播客：第几集")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args(argv)

    ident = grab(args.url, args.lang, args.episode)

    import store
    directory = Path(store.DATA) / "jobs" / ident
    data = json.loads((directory / "transcript.json").read_text(encoding="utf-8"))
    prof = facts.profile(data.get("segments") or [])
    segments = data.get("segments") or []

    rows = facts.build(segments, args.top) if args.facts else None
    pack = facts.build_steps(segments) if args.steps else None

    if args.json:
        print(json.dumps({"job": ident, "dir": str(directory), "profile": prof,
                          "media": str(facts.find_media(directory) or ""),
                          "facts": rows, "steps": pack}, ensure_ascii=False, indent=2))
        return

    written = []
    if args.facts:
        (directory / "facts.md").write_text(
            facts.render(ident, data, rows), encoding="utf-8")
        written.append(directory / "facts.md")
    if args.steps:
        (directory / "steps.md").write_text(
            facts.render_steps(ident, data, pack), encoding="utf-8")
        written.append(directory / "steps.md")

    print(facts.overview(directory, data, prof))
    if written:
        print("\n已写入：" + "、".join(str(p) for p in written), file=sys.stderr)


if __name__ == "__main__":
    main()
