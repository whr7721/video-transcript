"""关注源 → 扫出有没有更新。转不转、转哪条，另说。

    python follow.py add "https://www.douyin.com/user/MS4w..."   # 加一个人
    python follow.py                      # 扫一遍：共几条、最新哪条、有没有新的
    python follow.py new                  # 看有哪些新的还没转
    python follow.py run                  # 显式要转，才转
    python follow.py list                 # 看关注了谁

第一次扫描只建基线，不转写——否则新加一个人会把他的历史作品全转一遍。
基线之后，只把「上次扫描时还没有」的作品记成新的。

支持抖音博主主页、RSS/播客、YouTube 频道、B站 UP 主。单条视频用 grab.py。
"""
import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import store  # noqa: E402


def init():
    with store.connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS channels("
                   "id TEXT PRIMARY KEY,url TEXT UNIQUE NOT NULL,platform TEXT NOT NULL,payload TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS feed_items("
                   "seq INTEGER PRIMARY KEY AUTOINCREMENT,channel_id TEXT NOT NULL,content_id TEXT NOT NULL,"
                   "payload TEXT NOT NULL,UNIQUE(channel_id,content_id))")


def channels():
    init()
    with store.connect() as db:
        return [json.loads(r[0]) for r in db.execute("SELECT payload FROM channels ORDER BY rowid")]


def save_channel(channel):
    with store.connect() as db:
        db.execute("UPDATE channels SET payload=? WHERE id=?",
                   (json.dumps(channel, ensure_ascii=False), channel["id"]))


def find(prefix):
    """按 id 前缀找人，省得每次都粘 16 位。"""
    if not prefix:
        raise SystemExit("请指定源 id（先跑 follow.py list）")
    hits = [c for c in channels() if c["id"].startswith(prefix)]
    if not hits:
        raise SystemExit(f"没有 id 以 {prefix} 开头的关注源")
    if len(hits) > 1:
        raise SystemExit("id 前缀不唯一：" + "、".join(h["title"] for h in hits))
    return hits[0]


def normalize_url(text):
    """主页链接统一成不带 query 的形式；裸 sec_uid 直接当抖音博主。"""
    import re
    text = text.strip()
    if re.fullmatch(r"MS4wLj[A-Za-z0-9_-]{10,}", text):
        return "https://www.douyin.com/user/" + text
    import source_enumeration as sources
    kind, url = sources.identify(text)
    from urllib.parse import urlsplit, urlunsplit
    p = urlsplit(url)
    path = p.path.rstrip("/")
    if kind == "youtube":
        path = path.removesuffix("/videos").removesuffix("/shorts")
        return urlunsplit((p.scheme, "www.youtube.com", path, "", ""))
    if kind == "bilibili":
        return urlunsplit((p.scheme, p.netloc, "/" + path.strip("/").split("/")[0], "", ""))
    if kind == "douyin":
        return urlunsplit((p.scheme, "www.douyin.com", "/user/" + path.split("/user/")[1].split("/")[0], "", ""))
    if kind == "single":
        import link_ingest
        if link_ingest.platform(url) != "rss":
            raise ValueError("这里只收主页/频道/RSS；单条视频用 grab.py <链接>")
        return url
    return url


def cmd_add(args):
    init()
    try:
        url = normalize_url(args.url)
    except ValueError as exc:
        raise SystemExit(str(exc))
    import source_enumeration as sources
    kind, _ = sources.identify(url)
    kind = "rss" if kind == "single" else kind
    with store.connect() as db:
        old = db.execute("SELECT payload FROM channels WHERE url=?", (url,)).fetchone()
        if old:
            c = json.loads(old[0])
            print(f"已经在跟了：{c['title']}（{c['id'][:8]}）")
            return
        c = {"id": uuid.uuid4().hex[:16], "url": url, "platform": kind,
             "title": args.title or url, "added_at": time.time(),
             "last_check": None, "last_success": None, "initialized": False,
             "status": "idle", "error": None, "auto_extract": not args.no_auto}
        db.execute("INSERT INTO channels VALUES (?,?,?,?)",
                   (c["id"], url, kind, json.dumps(c, ensure_ascii=False)))
    print(f"已加：{c['title']}　id {c['id'][:8]}　平台 {kind}")
    print("下次 follow.py 会先建基线（只记录现有作品，不转写），再往后才转新的。")


def cmd_list(args):
    rows = channels()
    if not rows:
        print("还没有关注源。follow.py add <主页链接>")
        return
    with store.connect() as db:
        for c in rows:
            mark = "已建基线" if c.get("initialized") else "待建基线"
            err = f"　错误：{c['error']}" if c.get("error") else ""
            total = f"　共 {c['total']} 条作品" if c.get("total") else ""
            print(f"{c['id'][:8]}  {c['title']}　{c['platform']}{total}　{mark}{err}")
            last = db.execute("SELECT payload FROM feed_items WHERE channel_id=? "
                              "ORDER BY CAST(json_extract(payload,'$.published') AS INTEGER) DESC LIMIT 1",
                              (c["id"],)).fetchone()
            if last:
                row = json.loads(last[0])
                print(f"          最新 {stamp(row.get('published'))}　{short(row['title'], 40)}")
            print(f"          {c['url']}")
        total = db.execute("SELECT count(*) FROM feed_items").fetchone()[0]
        pending = db.execute("SELECT count(*) FROM feed_items WHERE "
                             "json_extract(payload,'$.job_id') IS NULL").fetchone()[0]
    print(f"\n共记录 {total} 条作品，{pending} 条还没转写。")


def check_one(channel, limit):
    """扫一个源，把新作品写进库里。返回 (新增条数, 是否是首次基线, 结果)。"""
    import source_enumeration as sources
    first = not channel.get("initialized")
    channel.update(status="checking", last_check=time.time(), error=None)
    save_channel(channel)
    try:
        result = sources.enumerate_source(channel["platform"], channel["url"], limit)
    except Exception as exc:
        channel.update(status="error", error=str(exc))
        save_channel(channel)
        raise

    fresh = 0
    with store.connect() as db:
        for row in reversed(result["items"]):     # 旧→新入库，seq 顺序即时间顺序
            exists = db.execute("SELECT payload FROM feed_items WHERE channel_id=? AND content_id=?",
                                (channel["id"], row["id"])).fetchone()
            if exists:
                # 热度会变，每次扫描刷新；read / job_id 这些本地状态不能丢。
                kept = json.loads(exists[0])
                kept.update({k: row.get(k) for k in
                             ("likes", "collects", "comments", "shares", "top", "duration", "published")})
                db.execute("UPDATE feed_items SET payload=? WHERE channel_id=? AND content_id=?",
                           (json.dumps(kept, ensure_ascii=False), channel["id"], row["id"]))
                continue
            payload = {**row, "read": False, "discovered_at": time.time(),
                       "job_id": None, "transcribed_at": None}
            db.execute("INSERT INTO feed_items(channel_id,content_id,payload) VALUES (?,?,?)",
                       (channel["id"], row["id"], json.dumps(payload, ensure_ascii=False)))
            fresh += 1
        channel.update(title=result.get("title") or channel["title"], total=result.get("total"),
                       initialized=True, status="idle",
                       last_success=time.time() if result.get("status") == "ok" else channel.get("last_success"))
        if result.get("status") != "ok":
            channel["status"] = "partial"
            channel["error"] = result.get("message")
        db.execute("UPDATE channels SET payload=? WHERE id=?",
                   (json.dumps(channel, ensure_ascii=False), channel["id"]))
    return fresh, first, result


def latest_of(result):
    """最近一条作品。列表一般已按时间倒序，但置顶会打乱，所以按发布时间取最大。"""
    items = result.get("items") or []
    return max(items, key=lambda r: r.get("published") or 0) if items else None


def cmd_check(args):
    rows = [find(args.only)] if args.only else channels()
    if not rows:
        print("还没有关注源。follow.py add <主页链接>")
        return
    started = time.time()
    total_new = 0
    for c in rows:
        try:
            fresh, first, result = check_one(c, args.limit)
        except Exception as exc:
            print(f"{c['title']}　扫描失败：{exc}")
            continue
        head = f"{c['title']}　共 {result['total']} 条作品" if result.get("total") else c["title"]
        head += f"　本次看最近 {len(result['items'])} 条"
        print(head)
        newest = latest_of(result)
        if newest:
            dur = f"　{newest['duration'] / 60:.0f} 分钟" if newest.get("duration") else ""
            print(f"    最新　{stamp(newest.get('published'))}{dur}　{heat(newest)}")
            print(f"          {short(newest['title'], 52)}")
        if first:
            print(f"    首次扫描：记下这 {fresh} 条当基线，一条也没转")
        elif fresh:
            print(f"    新增 {fresh} 条（follow.py new 看，run 转）")
            total_new += fresh
        else:
            print("    没有新的")
    print(f"\n扫了 {len(rows)} 个源，用时 {time.time() - started:.0f}s，新发现 {total_new} 条")


def pending():
    init()
    with store.connect() as db:
        return [dict(seq=r["seq"], channel_id=r["channel_id"], **json.loads(r["payload"]))
                for r in db.execute("SELECT seq,channel_id,payload FROM feed_items "
                                    "WHERE json_extract(payload,'$.job_id') IS NULL ORDER BY seq")]


def stamp(ts):
    if not ts:
        return "时间未知"
    return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")


def short(text, n=44):
    """作品描述常常是整段口播稿，取第一行再截断。"""
    line = (text or "").strip().splitlines()[0] if (text or "").strip() else "未命名"
    return line if len(line) <= n else line[:n] + "…"


def num(n):
    """播放量抖音已经不给（恒为 0），点赞收藏还在，这是判断哪条值得做的唯一现成信号。"""
    if n is None:
        return "—"
    if n >= 10000:
        return f"{n / 10000:.1f}万".replace(".0万", "万")
    return str(n)


def heat(row):
    bits = []
    if row.get("top"):
        bits.append("置顶")
    bits.append(f"赞 {num(row.get('likes'))}")
    if row.get("collects") is not None:
        bits.append(f"藏 {num(row.get('collects'))}")
    return "　".join(bits)


def cmd_new(args):
    rows = pending()
    if not rows:
        print("没有待转写的新作品。")
        return
    names = {c["id"]: c["title"] for c in channels()}
    for r in rows:
        dur = f"{r['duration'] / 60:.0f} 分钟" if r.get("duration") else "时长未知"
        print(f"[{r['seq']}] {stamp(r.get('published'))}　{names.get(r['channel_id'], '?')}　{dur}")
        print(f"      {short(r['title'])}")
        print(f"      {heat(r)}")
    print(f"\n共 {len(rows)} 条。follow.py run 转写。")


def cmd_run(args):
    rows = pending()
    if getattr(args, "seq", None):
        want = set(args.seq)
        rows = [r for r in rows if r["seq"] in want]
        missing = want - {r["seq"] for r in rows}
        if missing:
            print(f"这些 seq 不在待转列表里：{sorted(missing)}")
    if args.max:
        rows = rows[:args.max]
    if not rows:
        print("没有待转写的新作品。")
        return
    import contextlib

    import grab

    done = failed = 0
    for r in rows:
        print(f"\n=== {stamp(r.get('published'))}　{short(r['title'])}")
        try:
            with contextlib.redirect_stdout(sys.stderr):   # 底层模块往 stdout 吐路径，别混进结果里
                ident = grab.grab(r["url"])
        except SystemExit as exc:
            print(f"    跳过：{exc}")
            failed += 1
            continue
        except Exception as exc:
            print(f"    失败：{type(exc).__name__} {exc}")
            failed += 1
            with store.connect() as db:
                db.execute("UPDATE feed_items SET payload=? WHERE seq=?",
                           (json.dumps({**r, "error": str(exc)}, ensure_ascii=False), r["seq"]))
            continue
        with store.connect() as db:
            row = dict(r)
            for k in ("seq", "channel_id"):
                row.pop(k, None)
            row.update(job_id=ident, transcribed_at=time.time(), read=True, error=None)
            db.execute("UPDATE feed_items SET payload=? WHERE seq=?",
                       (json.dumps(row, ensure_ascii=False), r["seq"]))
        done += 1
        print(f"    已转写 → data/jobs/{ident}/transcript.txt")
    print(f"\n完成 {done} 条，失败 {failed} 条。")


def cmd_rm(args):
    c = find(args.only)
    with store.connect() as db:
        db.execute("DELETE FROM feed_items WHERE channel_id=?", (c["id"],))
        db.execute("DELETE FROM channels WHERE id=?", (c["id"],))
    print(f"已取消关注：{c['title']}（已转写的文稿保留在 data/jobs/）")


def cmd_sync(args):
    cmd_check(args)
    print()
    cmd_run(args)


def main(argv=None):
    parser = argparse.ArgumentParser(description="关注源 → 新作品 → 转写（自用）")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("add", help="加一个关注源")
    p.add_argument("url", help="抖音博主主页 / RSS / YouTube 频道 / B站空间")
    p.add_argument("--title", help="自定义备注名")
    p.add_argument("--no-auto", action="store_true", help="只扫描不自动转写（默认会转）")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list", help="看关注了谁")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("check", help="扫一遍有没有更新，不转写")
    p.add_argument("--limit", type=int, default=20, help="每次看最近几条，默认 20")
    p.add_argument("--only", help="只扫某个源（id 前缀）")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("new", help="看有哪些新作品还没转")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("run", help="转写还没转的新作品")
    p.add_argument("--max", type=int, help="这次最多转几条")
    p.add_argument("--seq", type=int, nargs="+", help="只转指定 seq（follow.py new 里那个编号）")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("rm", help="取消关注")
    p.add_argument("--only", required=True, help="源 id 前缀")
    p.set_defaults(func=cmd_rm)

    p = sub.add_parser("sync", help="扫一遍，并且把新作品转成文字")
    p.add_argument("--limit", type=int, default=20, help="每次看最近几条，默认 20")
    p.add_argument("--only", help="只扫某个源（id 前缀）")
    p.add_argument("--max", type=int, help="这次最多转几条")
    p.set_defaults(func=cmd_sync)

    args = parser.parse_args(argv)
    if args.cmd is None:                      # 不带子命令 = 只扫，不转
        args = argparse.Namespace(func=cmd_check, limit=20, only=None)
    args.func(args)


if __name__ == "__main__":
    main()
