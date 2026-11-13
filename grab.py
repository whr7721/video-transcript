"""自用入口：链接 → 转写稿 → 分类型产出。一条命令，不启动服务、不碰前端、不调用模型。

    python grab.py "https://www.xiaoyuzhoufm.com/episode/xxxx"
    python grab.py "https://www.bilibili.com/video/BVxxxx" --top 30

转完先判类型，再决定给你什么：

- **教程** → `steps.md`，按时间顺序的操作流 + 参数 + 坑。用来照着做，或者交给 AI 学。
- **案例** → `facts.md`，带时间码的事实卡。用来洗稿做知识动画。
- **观点** → `note.md`，一句话说清这条为什么不适合做动画。

转写在本机完成（SenseVoice INT8，约 30 倍实时，零费用）；判定和抽取是纯规则，不计配额。
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
    parser = argparse.ArgumentParser(description="链接 → 转写 + 分类型产出（自用）")
    parser.add_argument("url", help="视频/播客链接，或本地音视频路径")
    parser.add_argument("--top", type=int, default=40, help="案例型：输出多少条事实卡")
    parser.add_argument("--lang", default="auto", choices=["auto", "zh", "en", "ja", "ko", "yue"])
    parser.add_argument("--episode", type=int, help="RSS / 播客：第几集")
    parser.add_argument("--type", dest="force", default="auto",
                        choices=["auto", "tutorial", "case", "note"], help="强制类型，默认自动判")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    args = parser.parse_args(argv)

    ident = grab(args.url, args.lang, args.episode, args.top)

    import store
    directory = Path(store.DATA) / "jobs" / ident
    data = json.loads((directory / "transcript.json").read_text(encoding="utf-8"))
    kind, cls, payload = facts.analyze(data, args.force)

    if args.json:
        print(json.dumps({"job": ident, "dir": str(directory), "kind": kind,
                          "classify": cls, "payload": payload}, ensure_ascii=False, indent=2))
        return

    title = (data.get("title") or "未命名").replace("\n", " ").strip()
    if len(title) > 60:
        title = title[:60] + "…"
    print(f"\n{title}")
    print(f"{facts.stamp(data.get('duration') or 0)} ｜ {len(data.get('text') or '')} 字 ｜ "
          f"判为{facts.KIND_CN.get(kind, kind)}"
          f"（教程 {cls.get('tutorial', 0):.2f} / 案例 {cls.get('case', 0):.2f}）"
          f" ｜ {directory}\n")

    if kind == "tutorial":
        (directory / "steps.md").write_text(
            facts.render_steps(ident, data, cls, payload), encoding="utf-8")
        flow, warns = payload["flow"], payload["warns"]
        for i, row in enumerate(flow[:20], 1):
            mark = " ⚠" if row["warn"] else "  "
            print(f"{i:>2}{mark}{facts.stamp(row['t'])}  {row['text']}")
        if len(flow) > 20:
            print(f"… 还有 {len(flow) - 20} 条")
        print(f"\n共 {len(flow)} 步 ｜ {len(warns)} 个坑 ｜ 步骤单：{directory / 'steps.md'}")
    elif kind == "case":
        (directory / "facts.md").write_text(
            facts.render(ident, data, payload, cls), encoding="utf-8")
        for i, row in enumerate(payload, 1):
            mark = "★" if row["score"] >= 8 else " "
            print(f"{mark}{i:>2} {facts.stamp(row['t'])}  {row['text']}")
        strong = sum(1 for r in payload if r["score"] >= 8)
        print(f"\n强候选 {strong} 条 / 共 {len(payload)} 条 ｜ 事实表：{directory / 'facts.md'}")
    else:
        (directory / "note.md").write_text(
            facts.render_note(ident, data, cls), encoding="utf-8")
        print("没有可画的事实，也没有可照做的步骤——这条当选题灵感可以，当素材源不行。")
        print(f"判定：{directory / 'note.md'}")

    print(f"全文：{directory / 'transcript.txt'}")


if __name__ == "__main__":
    main()
