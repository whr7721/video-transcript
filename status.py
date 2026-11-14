"""拾文 · 本机状态自检。

一条命令看清：哪些站点的登录态还在、哪些没登过、抓取能力齐不齐、手上有多少东西。
不启动浏览器、不发任何网络请求，纯读本地文件，秒出。

    python status.py
    python status.py --json
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

DATA = Path(os.environ.get("SHIWEN_DATA_DIR", ROOT / "data")).resolve()

EPOCH = 1601
EPOCH_OFFSET_US = 11644473600 * 1_000_000

# 判定登录态看这几个 cookie；缺了就等于没登录
AUTH_KEYS = {
    "douyin.com": ("sessionid", "sessionid_ss", "sid_tt"),
    "xiaohongshu.com": ("web_session",),
    "bilibili.com": ("SESSDATA",),
    "weibo.com": ("SUB",),
}

SITE_NAMES = {
    "douyin.com": "抖音",
    "xiaohongshu.com": "小红书",
    "bilibili.com": "B站",
    "weibo.com": "微博",
}

LOGIN_HINT = {
    "douyin.com": 'python scrape.py --login "https://www.douyin.com"',
    "xiaohongshu.com": 'python scrape.py --login "https://www.xiaohongshu.com"',
    "bilibili.com": 'python scrape.py --login "https://www.bilibili.com"',
    "weibo.com": 'python scrape.py --login "https://weibo.com"',
}


def _to_dt(us):
    """Chromium 时间戳（1601 纪元，微秒）→ 本地 datetime。0 表示会话 cookie。"""
    if not us:
        return None
    try:
        return time.localtime((us - EPOCH_OFFSET_US) / 1_000_000)
    except (OSError, ValueError, OverflowError):
        return None


def _fmt(dt, with_year=True):
    if not dt:
        return "会话级"
    return time.strftime("%Y-%m-%d" if with_year else "%m-%d %H:%M", dt)


def profile_cookies(profile_dir):
    """读 Chromium profile 里的 Cookies 库，返回 [(host, name, expires, last_access)]。"""
    db_path = Path(profile_dir) / "Default" / "Network" / "Cookies"
    if not db_path.is_file():
        return []
    rows = []
    tmp = None
    try:
        # 浏览器可能正锁着这个库，先拷一份再读
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copy2(db_path, tmp)
        with sqlite3.connect(tmp) as db:
            for host, name, exp, acc in db.execute(
                "SELECT host_key, name, expires_utc, last_access_utc FROM cookies"
            ):
                rows.append((host, name, _to_dt(exp), _to_dt(acc)))
    except sqlite3.Error:
        return []
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return rows


def json_cookies(folder):
    """读 bilibili_auth / xhs_auth 导出的 cookie JSON。"""
    out = []
    folder = Path(folder)
    if not folder.is_dir():
        return out
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, list):
            out.append((path.stem, len(data)))
    return out


def check_sites():
    """每个站点：登录态在不在、依据是什么、什么时候看过。"""
    sources = [
        ("主 profile", DATA / "browser"),
        ("B站 profile", DATA / "browser-bilibili"),
        ("小红书 profile", DATA / "browser-xiaohongshu"),
    ]
    all_rows = []
    for label, path in sources:
        for host, name, exp, acc in profile_cookies(path):
            all_rows.append((label, host, name, exp, acc))

    result = []
    for domain, keys in AUTH_KEYS.items():
        hits = [r for r in all_rows if domain in r[1] and r[2] in keys]
        entry = {
            "domain": domain,
            "name": SITE_NAMES[domain],
            "logged_in": bool(hits),
            "where": None,
            "expires": None,
            "last_access": None,
            "hint": LOGIN_HINT[domain],
        }
        if hits:
            label, _host, _name, exp, acc = max(hits, key=lambda r: r[4] or 0)
            entry["where"] = label
            entry["expires"] = _fmt(exp)
            entry["last_access"] = _fmt(acc, with_year=False)
            # 有 cookie 但已过期，算掉了
            if exp and time.mktime(exp) < time.time():
                entry["logged_in"] = False
                entry["expired"] = True
        result.append(entry)
    return result, all_rows


def db_counts():
    """关注源、订阅条目数（读 tokens 都用同一个库）。"""
    info = {"channels": 0, "items": 0, "db": None}
    db_path = DATA / "tasks.sqlite3"
    if not db_path.is_file():
        return info
    info["db"] = db_path.stat().st_size
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5) as db:
            for table, key in (("channels", "channels"), ("feed_items", "items")):
                try:
                    info[key] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.Error:
                    pass
    except sqlite3.Error:
        pass
    return info


def watch_count():
    folder = DATA / "watch"
    if not folder.is_dir():
        return 0, []
    names = []
    for sub in folder.iterdir():
        if sub.is_dir() and (sub / "config.json").is_file():
            names.append(sub.name)
    return len(names), names


def job_stats():
    folder = DATA / "jobs"
    if not folder.is_dir():
        return 0, 0, None
    dirs = [d for d in folder.iterdir() if d.is_dir()]
    total = 0
    newest = None
    for d in dirs:
        try:
            mtime = d.stat().st_mtime
            if newest is None or mtime > newest:
                newest = mtime
        except OSError:
            pass
        for cur, _dirs, files in os.walk(d):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(cur, f))
                except OSError:
                    pass
    return len(dirs), total, newest


def deps():
    targets = [
        ("curl_cffi", "TLS 指纹伪装（--fast 快路径）"),
        ("trafilatura", "正文抽取（--fast）"),
        ("fitz", "PDF 解析"),
        ("playwright", "浏览器抓取"),
        ("httpx", "接口直连"),
        ("psutil", "进程与会话检查"),
    ]
    return [
        {"name": name, "ok": find_spec(name) is not None, "why": why}
        for name, why in targets
    ]


def hotwords():
    path = DATA / "hotwords.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return len(data) if isinstance(data, dict) else 0


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def collect():
    sites, _rows = check_sites()
    cookies = json_cookies(DATA / "cookies")
    counts = db_counts()
    wcount, wnames = watch_count()
    jcount, jsize, jnew = job_stats()
    return {
        "data_dir": str(DATA),
        "sites": sites,
        "cookie_exports": cookies,
        "follow": counts,
        "watch": {"count": wcount, "names": wnames},
        "jobs": {
            "count": jcount,
            "size": jsize,
            "newest": time.strftime("%Y-%m-%d %H:%M", time.localtime(jnew)) if jnew else None,
        },
        "deps": deps(),
        "hotwords": hotwords(),
    }


def render(info):
    lines = []
    add = lines.append
    add("拾文 · 本机状态")
    add("=" * 52)
    add("")
    add("登录态（没登录的站只能抓公开页，且大概率被拦）")
    for s in info["sites"]:
        if s["logged_in"]:
            mark = "OK  "
            note = f"{s['where']} · 有效期至 {s['expires']} · 最后活动 {s['last_access']}"
        elif s.get("expired"):
            mark = "过期"
            note = f"cookie 已过期（{s['expires']}），重新登录：{s['hint']}"
        else:
            mark = "未登"
            note = s["hint"]
        add(f"  [{mark}] {s['name']:<4} {note}")
    if info["cookie_exports"]:
        add("")
        add("  已导出 cookie：" + "、".join(f"{n}({c} 条)" for n, c in info["cookie_exports"]))
    else:
        add("")
        add("  已导出 cookie：无（data/cookies 为空，B站/小红书还没走过 cookie 通道）")

    add("")
    add("手上的东西")
    f = info["follow"]
    add(f"  关注源    {f['channels']} 个" + (f"，累计 {f['items']} 条作品" if f["items"] else ""))
    w = info["watch"]
    add(f"  监控项    {w['count']} 个" + (f"（{'、'.join(w['names'][:3])}）" if w["names"] else ""))
    j = info["jobs"]
    add(f"  转写任务  {j['count']} 个 · {human(j['size'])}" + (f" · 最近 {j['newest']}" if j["newest"] else ""))
    add(f"  纠错词表  {info['hotwords']} 条")

    add("")
    add("能力")
    bad = [d for d in info["deps"] if not d["ok"]]
    for d in info["deps"]:
        add(f"  [{'OK' if d['ok'] else '缺'}] {d['name']:<12} {d['why']}")
    if bad:
        add("")
        add(f"  缺 {len(bad)} 项，装： pip install " + " ".join(
            "PyMuPDF" if d["name"] == "fitz" else d["name"] for d in bad))

    add("")
    add("=" * 52)
    need = [s["name"] for s in info["sites"] if not s["logged_in"]]
    if need:
        add(f"要补登录态：{'、'.join(need)}（命令见上）")
    else:
        add("四个站都在线，直接抓。")
    add("抓不动先看 BOUNDARY.md，别反复重试。")
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    info = collect()
    if "--json" in argv:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(render(info))


if __name__ == "__main__":
    main()
