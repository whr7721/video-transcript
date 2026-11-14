"""拾文 · 本机状态自检。

两种模式：

    python status.py           # 快（0.1 秒）：读本地 cookie 库 + 上次实测记录
    python status.py --live    # 真（3~5 秒）：解密 cookie，直接问服务端"还认不认"

**为什么要 --live**：cookie 在本地库里没过期，不等于服务端还认。
小红书就是典型——`web_session` 标到 2027 年，实际早被判废，一请求 `302 /login`。
只看本地时间戳会得出"登录有效"的错误结论。

不启动浏览器、不把任何 cookie 值写到磁盘。
"""
import base64
import ctypes
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from ctypes import wintypes
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
PROFILE = DATA / "browser"
KNOWN = DATA / "sites-known.json"

CHROME_EPOCH_OFFSET_US = 11644473600 * 1_000_000
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

SITES = {
    "douyin.com": {
        "name": "抖音",
        "keys": ("sessionid", "sessionid_ss", "sid_tt"),
        "login": 'python scrape.py --login "https://www.douyin.com"',
        "probe": None,  # 签名鉴权，纯请求判不了
        "note": "签名由页面 JS 算，只能开浏览器验（scrape.py 打开任一搜索页看是否跳登录）",
    },
    "xiaohongshu.com": {
        "name": "小红书",
        "keys": ("web_session",),
        "login": 'python scrape.py --login "https://www.xiaohongshu.com"',
        "probe": "xhs",
    },
    "bilibili.com": {
        "name": "B站",
        "keys": ("SESSDATA",),
        "login": 'python scrape.py --login "https://www.bilibili.com"',
        "probe": "bili",
        "note": "游客态可读公开视频、评论、热门榜，不影响抓",
    },
    "weibo.com": {
        "name": "微博",
        "keys": ("SUB",),
        "login": 'python scrape.py --login "https://weibo.com"',
        "probe": None,
    },
    "kuaishou.com": {
        "name": "快手",
        "keys": ("kuaishou.server.webday7_st", "kuaishou.server.webday7_ph",
                 "kuaishou.server.web_st", "userId"),
        "login": 'python scrape.py --login "https://www.kuaishou.com/new-reco" --login-auto 300',
        "probe": "kuaishou",
        "note": "graphql 要 __NS_sig3 签名，纯请求只有热榜这类白名单查询能过；抓内容走浏览器",
    },
}

STATE_LABEL = {
    "ok": "可用",
    "guest": "游客态",
    "expired": "已失效",
    "none": "未登录",
    "unknown": "未验证",
}


# ---------------------------------------------------------------- cookie 读取

def _dpapi(blob):
    """Windows DPAPI 解密主密钥。"""
    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    src = BLOB(len(blob), ctypes.cast(ctypes.create_string_buffer(blob, len(blob)),
                                      ctypes.POINTER(ctypes.c_char)))
    dst = BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst)):
        raise OSError("DPAPI 解密失败")
    n = dst.cbData
    buf = ctypes.create_string_buffer(n)
    ctypes.memmove(buf, dst.pbData, n)
    ctypes.windll.kernel32.LocalFree(dst.pbData)
    return buf.raw


def _aes_key(profile):
    path = Path(profile) / "Local State"
    if not path.is_file():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        raw = base64.b64decode(meta["os_crypt"]["encrypted_key"])[5:]  # 去掉 b"DPAPI"
        return _dpapi(raw)
    except (OSError, KeyError, ValueError):
        return None


def _decrypt(value, host, key):
    if not value or key is None:
        return ""
    if value[:3] not in (b"v10", b"v11"):
        try:
            return _dpapi(value).decode("utf-8", "replace")
        except OSError:
            return ""
    try:
        from Crypto.Cipher import AES
    except ImportError:
        return ""
    try:
        raw = AES.new(key, AES.MODE_GCM, nonce=value[3:15]).decrypt_and_verify(value[15:-16], value[-16:])
    except ValueError:
        return ""
    # Chrome 130+ 在明文前插了 32 字节 SHA256(host_key)，防止 cookie 库被整个拷走
    if len(raw) > 32 and raw[:32] == hashlib.sha256(host.encode()).digest():
        raw = raw[32:]
    return raw.decode("utf-8", "replace")


def _cookie_rows(profile):
    """[(host, name, expires, last_access, encrypted_value)]，库被占用时读副本。"""
    db_path = Path(profile) / "Default" / "Network" / "Cookies"
    if not db_path.is_file():
        return []
    tmp = None
    rows = []
    try:
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copy2(db_path, tmp)
        # 复制成功后再用只读连接打开，避免在浏览器运行时被 WAL 锁住
        with sqlite3.connect(tmp) as db:
            rows = db.execute(
                "SELECT host_key, name, expires_utc, last_access_utc, encrypted_value FROM cookies"
            ).fetchall()
    except sqlite3.Error:
        return []
    except PermissionError:
        # Windows 上 Chromium 打开 profile 时会独占 Cookies 文件
        raise SystemExit(
            "cookie 库被浏览器独占：有 Chromium（拾文登录窗口 / 抓取进程）正在用\n"
            f"  {db_path}\n"
            "把那个窗口关掉再跑，或者等抓取结束。"
        )
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return rows


def _fmt(us, pattern="%Y-%m-%d"):
    if not us:
        return "会话级"
    try:
        return time.strftime(pattern, time.localtime((us - CHROME_EPOCH_OFFSET_US) / 1_000_000))
    except (OSError, ValueError, OverflowError):
        return "?"


# ---------------------------------------------------------------- 真实探测

def probe_xhs(jar):
    """小红书：/explore 若 302 去 /login，说明服务端已判废。"""
    if "web_session" not in jar:
        return "none", "无 web_session"
    from curl_cffi import requests as creq
    r = creq.get("https://www.xiaohongshu.com/explore", cookies=jar, impersonate="chrome",
                 allow_redirects=False, timeout=15,
                 headers={"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"})
    if r.status_code in (301, 302, 303, 307):
        loc = r.headers.get("location", "")
        if "login" in loc:
            return "expired", "/explore → 302 /login（本地 cookie 未过期，服务端已判废）"
        return "expired", f"/explore → {r.status_code} {loc[:50]}"
    if r.status_code == 200 and len(r.text) > 50_000:
        return "ok", f"/explore 200，返回 {len(r.text) // 1000} KB 正常页面"
    return "unknown", f"/explore {r.status_code}，{len(r.text)} 字节，判不了"


def probe_bili(jar):
    """B站：nav 接口的 isLogin 是官方口径。"""
    from curl_cffi import requests as creq
    r = creq.get("https://api.bilibili.com/x/web-interface/nav", cookies=jar, impersonate="chrome",
                 timeout=15,
                 headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/"})
    try:
        data = r.json()
    except ValueError:
        return "unknown", f"nav 返回非 JSON（{r.status_code}）"
    payload = data.get("data") or {}
    if data.get("code") == 0 and payload.get("isLogin") is True:
        return "ok", f"nav isLogin=true，{payload.get('uname') or '已登录'}"
    if "SESSDATA" not in jar:
        return "guest", "nav isLogin=false，无 SESSDATA——公开接口、评论、热门榜照样能读"
    return "expired", f"nav code={data.get('code')} isLogin={payload.get('isLogin')}"


def probe_kuaishou(jar):
    """快手：所有接口都要 __NS_hxfalcon 签名，纯请求只能看出"有没有身份"，看不出"认不认"。

    实测（2026-11-14）：带 cookie 打 /rest/wd/user/profile 返回
    result=2001 antispam need captcha；打 /rest/v/profile/get 返回
    {"result":50,"error_msg":"签名验证失败"}。两者都不是"登录有效"的证据，
    所以这里只做诚实判断，真正的确认要开浏览器看 profile/get 的 result 是否为 1。
    """
    has_id = any(k.startswith("kuaishou.server.") for k in jar) or "userId" in jar
    if not has_id:
        return "none", "无 kuaishou.server.webday7_st 与 userId"
    from curl_cffi import requests as creq
    try:
        r = creq.get("https://www.kuaishou.com/rest/wd/user/profile",
                     params={"userId": jar.get("userId", "")},
                     cookies=jar, impersonate="chrome", timeout=15,
                     headers={"User-Agent": UA, "Referer": "https://www.kuaishou.com/",
                              "Accept": "application/json, text/plain, */*"})
        body = r.json()
    except Exception as exc:
        return "unknown", f"探测失败：{type(exc).__name__}"
    res = body.get("result")
    if res == 2001:
        return "unknown", ("本地有登录 cookie，接口回 2001 antispam（缺 __NS_hxfalcon 签名）"
                           "——纯请求判不了，浏览器开 profile 页看是否显示「登录即可享受」")
    if res == 2:
        return "expired", "接口回 result=2，服务端不认这份 cookie"
    return "unknown", f"接口回 result={res}，判不了"


def probe_kuaishou_browser(profile):
    """快手真正的判活：开浏览器，读页面自身发的 rest/v/profile/get 的 result。

    纯请求一律 50（签名验证失败）或 2001（antispam），只有页面里算得出的
    __NS_hxfalcon 才过。实测 result=1 是真登录、109 是未登录。
    """
    import asyncio
    import json as _json

    got = {}

    async def run():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                str(profile), headless=True, args=["--no-proxy-server"],
                viewport={"width": 1440, "height": 900}, locale="zh-CN")
            try:
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()

                async def on_resp(r):
                    if "rest/v/profile/get" in r.url:
                        try:
                            got["body"] = _json.loads(await r.text())
                        except Exception:
                            pass

                page.on("response", on_resp)
                await page.goto("https://www.kuaishou.com/new-reco",
                                wait_until="domcontentloaded", timeout=45000)
                for _ in range(20):
                    await asyncio.sleep(1)
                    if got.get("body"):
                        break
            finally:
                await ctx.close()

    try:
        asyncio.run(run())
    except Exception as exc:
        return "unknown", f"浏览器探测失败：{type(exc).__name__}"

    body = got.get("body") or {}
    res = body.get("result")
    if res == 1:
        return "ok", (f"profile/get result=1，{body.get('userName') or '已登录'}"
                      f" · 粉丝 {body.get('fans')} · 关注 {body.get('follows')}")
    if res == 109:
        return "expired", "profile/get result=109，服务端不认这份登录态（需重登）"
    if res == 50:
        return "unknown", "profile/get result=50 签名验证失败（浏览器被识别）"
    return "unknown", f"profile/get result={res}，判不了"


PROBES = {"xhs": probe_xhs, "bili": probe_bili, "kuaishou": probe_kuaishou}
BROWSER_PROBES = {"kuaishou": probe_kuaishou_browser}


# ---------------------------------------------------------------- 实测记录

def load_known():
    if not KNOWN.is_file():
        return {}
    try:
        data = json.loads(KNOWN.read_text(encoding="utf-8"))
        return data.get("sites", {}) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_known(sites):
    try:
        KNOWN.parent.mkdir(parents=True, exist_ok=True)
        KNOWN.write_text(json.dumps({"version": 1, "sites": sites}, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    except OSError:
        pass


def ago(iso):
    try:
        delta = time.time() - time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M"))
    except (ValueError, OverflowError):
        return "?"
    if delta < 3600:
        return f"{int(delta // 60)} 分钟前"
    if delta < 86400:
        return f"{int(delta // 3600)} 小时前"
    return f"{int(delta // 86400)} 天前"


# ---------------------------------------------------------------- 汇总

def collect(live=False, browser=False):
    rows = _cookie_rows(PROFILE)
    key = _aes_key(PROFILE) if live else None
    known = load_known()

    out = []
    for domain, cfg in SITES.items():
        mine = [r for r in rows if domain in r[0] and r[1] in cfg["keys"]]
        item = {
            "domain": domain,
            "name": cfg["name"],
            "local": bool(mine),
            "expires": None,
            "last_access": None,
            "state": "none",
            "evidence": "",
            "checked": None,
            "login": cfg["login"],
            "note": cfg.get("note", ""),
        }
        if mine:
            _h, _n, exp, acc, _v = max(mine, key=lambda r: r[3] or 0)
            item["expires"] = _fmt(exp)
            item["last_access"] = _fmt(acc, "%m-%d %H:%M")
            # 本地有 cookie 只说明"登过"，不代表服务端还认——先记未验证
            item["state"] = "unknown"
            item["evidence"] = (f"本地有 {mine[0][1]}，标称有效期至 {item['expires']}，"
                                f"最后一次写入 {item['last_access']}——未经服务端确认")

        # 上次实测结论先垫底，--live 跑通就覆盖
        prev = known.get(domain)
        if prev:
            item["state"] = prev.get("state", "unknown")
            item["evidence"] = prev.get("evidence", "")
            item["checked"] = prev.get("at")

        if live and cfg["probe"]:
            if cfg["probe"] in BROWSER_PROBES and browser:
                try:
                    state, evidence = BROWSER_PROBES[cfg["probe"]](PROFILE)
                except Exception as exc:
                    state, evidence = "unknown", f"浏览器探测失败：{type(exc).__name__}"
            elif cfg["probe"] in BROWSER_PROBES:
                state, evidence = ("unknown",
                                   "签名站，纯请求判不了；加 --browser 开浏览器做真实探测")
            else:
                jar = {}
                for host, name, _exp, _acc, enc in rows:
                    if domain in host:
                        val = _decrypt(enc, host, key)
                        if val:
                            jar[name] = val
                try:
                    state, evidence = PROBES[cfg["probe"]](jar)
                except Exception as exc:  # 网络错误不该让整条命令挂掉
                    state, evidence = "unknown", f"探测失败：{type(exc).__name__}"
            # 探测不出结论（签名站、网络抖）时，不要覆盖掉之前人工确认过的结论
            if state == "unknown" and prev and prev.get("state") in ("ok", "guest"):
                state, evidence = prev["state"], prev.get("evidence", "")
            item["state"], item["evidence"] = state, evidence
            item["checked"] = time.strftime("%Y-%m-%dT%H:%M")
            known[domain] = {"state": state, "evidence": evidence, "at": item["checked"]}

        out.append(item)

    if live:
        save_known(known)
    return out


def db_counts():
    info = {"channels": 0, "items": 0}
    path = DATA / "tasks.sqlite3"
    if not path.is_file():
        return info
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5) as db:
            for table, key in (("channels", "channels"), ("feed_items", "items")):
                try:
                    info[key] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.Error:
                    pass
    except sqlite3.Error:
        pass
    return info


def watch_items():
    folder = DATA / "watch"
    if not folder.is_dir():
        return []
    return [d.name for d in folder.iterdir() if d.is_dir() and (d / "config.json").is_file()]


def job_stats():
    folder = DATA / "jobs"
    if not folder.is_dir():
        return 0, 0, None
    count = size = 0
    newest = None
    for d in folder.iterdir():
        if not d.is_dir():
            continue
        count += 1
        try:
            m = d.stat().st_mtime
            newest = m if newest is None or m > newest else newest
        except OSError:
            pass
        for cur, _dirs, files in os.walk(d):
            for f in files:
                try:
                    size += os.path.getsize(os.path.join(cur, f))
                except OSError:
                    pass
    return count, size, (time.strftime("%Y-%m-%d %H:%M", time.localtime(newest)) if newest else None)


def hotword_count():
    path = DATA / "hotwords.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return len(data) if isinstance(data, dict) else 0


def deps():
    return [(n, find_spec(n) is not None, why) for n, why in [
        ("curl_cffi", "TLS 指纹伪装（--fast / 真实探测）"),
        ("trafilatura", "正文抽取（--fast）"),
        ("fitz", "PDF 解析"),
        ("playwright", "浏览器抓取"),
        ("httpx", "接口直连"),
        ("Crypto", "cookie 解密（--live）"),
    ]]


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def render(sites, live=False):
    L = []
    add = L.append
    add("拾文 · 本机状态" + ("（已问过服务端）" if live else "（本地记录）"))
    add("=" * 60)
    add("")
    for s in sites:
        add(f"  {s['name']:<4} {STATE_LABEL[s['state']]}")
        if s["state"] in ("ok", "guest", "expired"):
            add(f"        {s['evidence']}")
            if s["state"] == "expired":
                add(f"        重登：{s['login']}")
        elif s["state"] == "none":
            add(f"        本地无记录 · 登录：{s['login']}")
            if s["note"]:
                add(f"        {s['note']}")
        else:
            add(f"        {s['evidence'] or s['note'] or '还没验过，跑 --live'}")
        if s["checked"]:
            add(f"        实测于 {ago(s['checked'])}")
        add("")

    follow = db_counts()
    watches = watch_items()
    jobs, size, newest = job_stats()
    add("手上的东西")
    add(f"  关注源    {follow['channels']} 个" + (f"，累计 {follow['items']} 条作品" if follow["items"] else ""))
    add(f"  监控项    {len(watches)} 个" + (f"（{'、'.join(watches[:3])}）" if watches else ""))
    add(f"  转写任务  {jobs} 个 · {human(size)}" + (f" · 最近 {newest}" if newest else ""))
    add(f"  纠错词表  {hotword_count()} 条")

    add("")
    add("能力")
    for name, ok, why in deps():
        add(f"  [{'OK' if ok else '缺'}] {name:<12} {why}")

    add("")
    add("=" * 60)
    if not live:
        add("这些是本地记录，不代表服务端还认。要看真的：status.py --live")
    else:
        todo = [s["name"] for s in sites if s["state"] in ("expired", "none")]
        if todo:
            add(f"要补登录态：{'、'.join(todo)}（命令在上面）")
        else:
            add("都在可用状态。")
    add("抓不动先看 BOUNDARY.md，别反复重试。")
    return "\n".join(L)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    # 抖音这类纯请求判不了的，允许人工记一笔：
    #   python status.py --set douyin.com=ok "浏览器开搜索页返回笔记标题/作者/点赞"
    if "--set" in argv:
        i = argv.index("--set")
        spec = argv[i + 1] if len(argv) > i + 1 else ""
        note = argv[i + 2] if len(argv) > i + 2 else ""
        if "=" not in spec:
            print('用法：status.py --set douyin.com=ok "依据"')
            return 2
        domain, state = spec.split("=", 1)
        if state not in STATE_LABEL:
            print(f"状态只能是：{' / '.join(STATE_LABEL)}")
            return 2
        known = load_known()
        known[domain] = {"state": state, "evidence": note,
                         "at": time.strftime("%Y-%m-%dT%H:%M")}
        save_known(known)
        print(f"已记录：{domain} = {state}（{note or '无依据'}）")
        return 0

    live = "--live" in argv
    sites = collect(live=live, browser="--browser" in argv)
    if "--json" in argv:
        print(json.dumps({"live": live, "sites": sites}, ensure_ascii=False, indent=2))
    else:
        print(render(sites, live=live))
    return 0


if __name__ == "__main__":
    main()
