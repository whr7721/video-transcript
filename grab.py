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


def guard_url(url):
    """不是单条作品的链接，报错要说清该走哪条路。

    底层只会说「无法取得作品编号」，或者把 HTML 当 RSS 解析后报
    「不支持含 DTD 的 RSS」，读起来都像链接坏了，agent 会反复重试。
    这里提前判形态，把三种情况分开说：

    - 主页 / 频道 → follow.py 扫
    - 榜单 / 活动 / 专题 / 搜索页 → 本工具不做，用浏览器现场抓
    - 快手 → 本工具不支持，同上
    """
    low = url.lower()
    path = low.split("?")[0]

    if "kuaishou.com" in low:
        raise SystemExit(
            "快手不在支持范围，本工具只认单条作品：\n"
            "  抖音 / 小红书 / B站 / YouTube / TikTok / X / 小宇宙 / Spotify / RSS / 本地文件。\n"
            "  要抓快手，用 scrape.py 开浏览器读页面（见 SKILL.md「页面型内容」）。\n"
            "  还没登录过就先跑：scrape.py --login \"https://www.kuaishou.com\"")

    if "douyin.com" in low or "iesdouyin.com" in low:
        single = ("/video/" in path or "/note/" in path or "/share/video/" in path
                  or "/share/note/" in path or "v.douyin.com" in low)
        if single:
            return
        if "/user/" in path or "/share/user/" in path:
            raise SystemExit(
                f"这是抖音博主主页，不是单条作品，所以取不到作品编号。\n"
                f"  看它有哪些内容、最新一条是什么：follow.py add \"{url}\" 然后 follow.py\n"
                f"  只转其中一条：把那条作品的链接给我")
        raise SystemExit(
            f"这是抖音的页面（榜单 / 活动 / 专题 / 搜索 / 合集），不是单条作品。\n"
            f"  本工具只处理单条作品和博主主页，页面型内容要自己开浏览器读。\n"
            f"  做法见 SKILL.md「页面型内容」：复用 data/browser 登录态，读 DOM 或拦 XHR，\n"
            f"  签名（a_bogus / msToken）由页面自己的 JS 算，不用你管。\n"
            f"  从页面上拿到具体作品链接之后，再喂给本工具转写。")

    try:
        import source_enumeration as sources
        kind, _ = sources.identify(url)
    except Exception:
        return
    hint = {"youtube": "YouTube 频道", "bilibili": "B站 UP 主主页",
            "rss": "RSS / 播客订阅源"}.get(kind)
    if hint:
        raise SystemExit(
            f"这是{hint}，不是单条作品，所以取不到作品编号。\n"
            f"  看它有哪些内容、最新一条是什么：follow.py add \"{url}\" 然后 follow.py\n"
            f"  只转其中一条：把那条作品的链接给我")


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

    guard_url(args.url)
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
