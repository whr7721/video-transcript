"""页面抓取：用登录态浏览器打开任意页面，按需要取 DOM / 文本 / XHR / 截图。

榜单、活动页、专题页、搜索结果 —— 这类内容没有固定接口，每次取法都不一样，
但骨架是同一个：开浏览器 → 等加载 → 滚动 → 取值。这个文件就是那个骨架。

    python scrape.py <url> --text                            # 整页文字
    python scrape.py <url> --selector "a[href*='/video/']"   # 元素文本
    python scrape.py <url> --selector "a.video" --attr href  # 取属性
    python scrape.py <url> --xhr "/aweme/v1/web/"            # 拦接口响应
    python scrape.py <url> --js "document.title"             # 任意提取
    python scrape.py <url> --scroll 5 --shot page.png        # 边滚边截图
    python scrape.py <url> --fast                            # 不开浏览器，直接拿正文
    python scrape.py <url> --selector ".item" --pages 10 --next "a.next"   # 翻页并去重
    python scrape.py --login <url>                           # 新建登录态，扫码后回车
    python scrape.py --login <url> --login-auto 180          # 同上但不用回车，登录成功自动保存关闭

公共参数：--profile（默认 data/browser）、--wait 秒、--json、--out 文件。

签名不用管：页面自己的 JS 会算 a_bogus / msToken，浏览器带着走。

--fast 是快路径：用 curl_cffi 伪装 Chrome 的 TLS 指纹直接发 HTTP，拿 trafilatura
提正文，0.2 秒一页。只对「服务端直出 HTML」的页面有效（政府公告、新闻、博客、
文档站），遇到前端渲染页或反爬挑战会自动降级到浏览器，并在 stderr 说明原因。
"""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DEFAULT_PROFILE = ROOT / "data" / "browser"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 抖音的 webid / msToken 是按 UA + 屏幕分辨率生成的，换 UA 就破坏了 webid 与 UA 的
# 一致性，服务端 a_bogus 校验直接失败——现象像「登录态失效」，实际是自己把环境改坏了。
UA_LOCKED_HOSTS = ("douyin.com", "iesdouyin.com")

# 反爬挑战页的特征。命中就不必再解析了，直接降级浏览器让人去看。
CHALLENGE_MARKS = ("Just a moment", "cf-challenge", "Checking your browser",
                   "Attention Required", "人机验证", "安全验证", "滑动验证",
                   "请开启JavaScript", "访问过于频繁")

PICK = """([sel, attr]) => Array.from(document.querySelectorAll(sel))
    .map(e => attr ? e.getAttribute(attr) : e.innerText)
    .map(s => (s || '').replace(/\\s+/g, ' ').trim())
    .filter(s => s.length > 0)"""


def guard_ua(url, ua):
    """抖音场景禁止覆盖 UA。"""
    if not ua or ua == "-":
        return
    host = urlsplit(url).netloc.lower()
    if any(host == h or host.endswith("." + h) for h in UA_LOCKED_HOSTS):
        raise SystemExit(
            "拒绝覆盖 UA：抖音的 webid 与 User-Agent 绑定，换 UA 会导致 a_bogus "
            "签名校验失败，看起来像登录态失效。抖音场景请去掉 --ua。"
        )


def decode_html(resp):
    """国内站点一半是 gb18030，按顺序试。"""
    raw = resp.content
    for enc in ("utf-8", "gb18030", "big5"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def strip_tags(html):
    """把 HTML 抹成纯文字，保留换行。列表页、首页只能靠这个。"""
    text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</(p|div|li|tr|h[1-6])>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&#160;", " ")
                .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"(\s*\n\s*){2,}", "\n", text)
    return text.strip()


def fast_fetch(url, timeout, whole=False):
    """不开浏览器直接拿正文。返回 (payload, reason)，失败时 payload 为 None。

    两级取法，失败原因必须分清，否则会误导成「这站抓不到」：
      1. trafilatura 找主文章 —— 适合新闻、公告、博客的正文页，输出干净无导航。
      2. 去标签全文（whole=True 强制，或在 1 失败时自动兜底）—— 适合列表页、
         首页、搜索结果页，这些页面本来就没有「一篇主文章」，只有一堆块。
    三种失败长得很像但完全不同：
      - HTML 里真没字（SPA 壳、跳转页）→ 只能开浏览器
      - HTML 里有字但没主文章（列表页）→ 用 raw 兜底，不是失败
      - 反爬挑战页 → 换浏览器带登录态
    """
    try:
        from curl_cffi import requests as creq
    except ImportError:
        return None, "curl_cffi 未安装（pip install curl_cffi trafilatura）"
    try:
        r = creq.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
    except Exception as exc:
        hint = ""
        if any(k in str(exc) for k in ("Timeout", "timed out", "CONNECT", "Connection")):
            hint = "（外网站点检查代理：$https_proxy / $http_proxy）"
        return None, f"{type(exc).__name__}: {exc}"[:100] + hint
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"

    html = decode_html(r)
    for mark in CHALLENGE_MARKS:
        if mark in html:
            return None, f"反爬挑战页（{mark}）"

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = strip_tags(m.group(1)) if m else ""

    text, mode = "", "fast"
    if not whole:
        try:
            import trafilatura
            text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
        except ImportError:
            pass
        if len(text) < 200:                   # 没主文章：列表页、首页的常态，用全文兜底
            raw = strip_tags(html)
            if len(raw) >= 200:
                text, mode = raw, "fast-raw"

    if len(text) < 200:
        raw = strip_tags(html)
        if len(raw) < 200:
            return None, (f"HTML 里没有正文（可见文字仅 {len(raw)} 字，多为前端渲染页或跳转壳页）")
        text, mode = raw, "fast-raw"

    return {"url": url, "title": title, "mode": mode, "chars": len(text), "data": text}, None


def clean_needle(text):
    """Git Bash 会把以 / 开头的参数当成路径，改写成 C:/Program Files/Git/...

    于是 --xhr "/aweme/v1/web/" 变成 C:/Program Files/Git/aweme/v1/web/，
    永远匹配不上，而且不报错，只是安静地返回 0 条。这里把被改写的部分剥回来。
    参数写成不带开头斜杠的 aweme/v1/web 本来就不会被改写，两种都认。
    """
    if not text:
        return text
    for marker in ("/Git/", "\\Git\\"):
        if marker in text:
            text = text.split(marker, 1)[1]
    return text.strip("/\\")


def key_of(item, field=None):
    """去重用的键。给了字段就按字段，否则按整条内容。"""
    if isinstance(item, dict):
        if field:
            return str(item.get(field, ""))
        return json.dumps(item, sort_keys=True, ensure_ascii=False)
    return str(item)


def with_page(url, param, page_no):
    """把 URL 里的 page 参数换成指定页码，其余参数原样保留。"""
    u = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k != param]
    q.append((param, str(page_no)))
    return urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), u.fragment))


async def grab(page, args):
    """只取值，不负责导航和等待。"""
    if args.js:
        return await page.evaluate(args.js)
    if args.selector:
        return await page.evaluate(PICK, [args.selector, args.attr])
    return await page.evaluate("document.body.innerText")


async def click_next(page, args):
    if args.next:
        loc = page.locator(args.next).first
        try:
            await loc.scroll_into_view_if_needed(timeout=6000)
            await loc.click(timeout=10000)
        except Exception as exc:
            raise SystemExit(
                f"点不到下一页元素 {args.next!r}：{type(exc).__name__}: {exc}\n"
                "先 --selector 数一下这个选择器能不能选中，或者改用 --page-param 翻页。")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=20000)
        except Exception:                      # 单页应用不触发 load，靠下面的等待兜底
            pass
        await page.wait_for_timeout(800)
    else:
        await page.mouse.wheel(0, 20000)       # 无限滚动：滚到底，等新内容加载
        await page.wait_for_timeout(2500)


async def paginate(page, args):
    """翻页 + 去重。返回 (本次新增, 统计, 全量)。

    去重是逐条做的：本页内重复、跨页重复、跟 --seen 基准重复，都算重复。
    某页返回 0 条就停——继续点下去只会拿到同一批东西或者错误页。
    """
    base = []
    seen = set()
    if args.seen:
        sp = Path(args.seen).expanduser()
        if sp.exists():
            try:
                old = json.loads(sp.read_text(encoding="utf-8"))
            except Exception:
                old = []
            if isinstance(old, dict):
                old = old.get("data", [])
            base = old if isinstance(old, list) else []
            seen = {key_of(x, args.dedupe) for x in base}
            print(f"[seen] 基准 {len(seen)} 条", file=sys.stderr)

    fresh, dupes, done = [], 0, 0
    for i in range(args.pages):
        if i == 0:
            await page.goto(args.url, wait_until=args.until, timeout=60000)
        elif args.page_param:
            await page.goto(with_page(args.url, args.page_param, args.page_start + i - 1),
                            wait_until=args.until, timeout=60000)
        else:
            await click_next(page, args)

        await page.wait_for_timeout(int(args.wait * 1000))
        for _ in range(args.scroll):
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(1200)

        chunk = await grab(page, args)
        if isinstance(chunk, (str, dict)):
            chunk = [chunk]
        chunk = [x for x in (chunk or []) if x not in (None, "")]

        new_here = 0
        for x in chunk:
            k = key_of(x, args.dedupe)
            if k in seen:
                dupes += 1
                continue
            seen.add(k)
            fresh.append(x)
            new_here += 1

        done = i + 1
        print(f"[page {done}/{args.pages}] 本页 {len(chunk)} 条，新增 {new_here}，"
              f"重复 {len(chunk) - new_here}", file=sys.stderr)
        if not chunk:
            print("[page] 本页 0 条，停止翻页（选择器可能失效，或已到末页）", file=sys.stderr)
            break

    return fresh, {"pages": done, "dupes": dupes, "new": len(fresh)}, base + fresh


async def run(args):
    guard_ua(args.url, args.ua)
    if args.fast_whole and not args.fast:
        print("[fast-whole] 只在 --fast 下生效，这次被忽略", file=sys.stderr)

    # 只有纯文字模式才走快路径：要选择器 / 要接口 / 要截图 / 要翻页，都必须有浏览器。
    pure_text = not (args.selector or args.js or args.xhr or args.xhr_list or args.shot)
    if args.fast and pure_text and args.pages == 1 and not args.login:
        payload, reason = fast_fetch(args.url, args.fast, args.fast_whole)
        if payload:
            text = json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["data"]
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8")
                print(f"写入 {Path(args.out).resolve()}", file=sys.stderr)
            else:
                sys.stdout.reconfigure(encoding="utf-8")
                print(text)
            tag = "" if payload["mode"] == "fast" else "（全文模式，含导航噪音）"
            print(f"[fast] {payload['chars']} 字，{payload['title'][:40]}{tag}", file=sys.stderr)
            return 0
        print(f"[fast] 降级到浏览器：{reason}", file=sys.stderr)

    from playwright.async_api import async_playwright

    profile = Path(args.profile).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    captured = []
    hits = [0]
    extra = {}

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(profile),
            headless=not (args.login or args.headed),
            args=["--no-proxy-server"],
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            user_agent=(args.ua or UA) if args.ua != "-" else None,
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            if args.login:
                await page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
                print(f"已打开 {args.url}", file=sys.stderr)
                if args.login_auto > 0:
                    # 无交互：登录成功后自动保存并关闭，供 agent 会话调用
                    print(f"请在那个窗口里扫码登录。轮询 cookie，最多等 {int(args.login_auto)} 秒。",
                          file=sys.stderr)
                    await asyncio.sleep(8)          # 让页面自身的匿名 cookie 先落定
                    base = await _auth_snapshot(ctx)
                    deadline = time.time() + args.login_auto
                    while time.time() < deadline:
                        await asyncio.sleep(2)
                        if page.is_closed():
                            print("[warn] 窗口被手动关闭，按已保存处理", file=sys.stderr)
                            break
                        cur = await _auth_snapshot(ctx)
                        changed = [k for k, v in cur.items() if base.get(k) != v]
                        if changed:
                            print(f"[ok] 检测到登录 cookie 变化：{', '.join(changed[:4])}，等 3 秒落盘",
                                  file=sys.stderr)
                            await asyncio.sleep(3)
                            break
                    else:
                        print("[timeout] 没检测到登录 cookie 变化，未确认登录成功", file=sys.stderr)
                        print("        已登录的站重跑也会这样（cookie 本来就不变）；扫码没结束就加大 SEC 重跑",
                              file=sys.stderr)
                        return 1
                    await ctx.close()
                    print(f"登录态已存到 {profile}", file=sys.stderr)
                    return 0
                print("在那个窗口里登录（扫码 / 验证码），完成后回终端按回车。", file=sys.stderr)
                await asyncio.get_event_loop().run_in_executor(None, input)
                print(f"登录态已存到 {profile}", file=sys.stderr)
                return 0

            if args.xhr or args.xhr_list:
                needle = clean_needle(args.xhr or args.xhr_list)

                async def collect(resp):
                    try:
                        body = await resp.text()
                    except Exception as exc:       # 响应体已释放 / 跨域拿不到
                        captured.append({"url": resp.url, "status": resp.status,
                                         "body": "", "error": f"{type(exc).__name__}: {exc}"[:120]})
                        return
                    captured.append({"url": resp.url, "status": resp.status, "body": body})

                def on_response(resp):
                    hits[0] += 1
                    if needle not in resp.url:
                        return
                    if args.xhr_list:
                        captured.append({"url": resp.url, "status": resp.status})
                    else:
                        asyncio.create_task(collect(resp))

                page.on("response", on_response)

            # --seen 单独用也有意义：单页增量（这个列表页有没有新东西），所以一并走批量分支。
            if args.pages > 1 or args.seen:
                if args.pages > 1 and (args.xhr or args.xhr_list):
                    raise SystemExit(
                        "--pages 不能和 --xhr 一起用：翻页会连续触发请求，多页的接口数据混在\n"
                        "一起分不清先后。先用 --xhr-list 找到接口地址，再用 --page-param 直接改 URL 翻页。")
                data, extra, merged = await paginate(page, args)
                title = await page.title()
                if args.seen:
                    sp = Path(args.seen).expanduser()
                    sp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"基准已更新 {sp.resolve()}（{len(merged)} 条）", file=sys.stderr)
                if not args.only_new:
                    data = merged
            else:
                await page.goto(args.url, wait_until=args.until, timeout=60000)
                await page.wait_for_timeout(int(args.wait * 1000))
                for _ in range(args.scroll):
                    await page.mouse.wheel(0, 3000)
                    await page.wait_for_timeout(1200)

                if args.xhr or args.xhr_list:
                    await page.wait_for_timeout(1500)
                    print(f"[监听] {hits[0]} 个响应，匹配 {len(captured)} 条", file=sys.stderr)
                    if args.xhr_list:
                        data = captured
                    elif args.xhr_parse:
                        data = []
                        for item in captured:
                            try:
                                parsed = json.loads(item["body"])
                            except Exception:
                                parsed = item["body"]
                            data.append({"url": item["url"], "status": item.get("status"),
                                         "error": item.get("error"), "body": parsed})
                    else:
                        data = captured
                else:
                    data = await grab(page, args)

                title = await page.title()
                if args.shot:
                    await page.screenshot(path=args.shot, full_page=False)
                    print(f"截图 {Path(args.shot).resolve()}", file=sys.stderr)
        finally:
            await ctx.close()

    if isinstance(data, list):
        mode = "xhr" if (args.xhr or args.xhr_list) else ("js" if args.js else "selector")
        envelope = {"url": args.url, "title": title, "mode": mode,
                    "count": len(data), "data": data, **extra}
    else:
        envelope = {"url": args.url, "title": title, "mode": "text", "data": data, **extra}

    if args.json or isinstance(data, (list, dict)):
        text = json.dumps(envelope, ensure_ascii=False, indent=2)
    else:
        text = data

    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"写入 {Path(args.out).resolve()}", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    return 0


AUTH_HINTS = ("session", "sess", "login", "token", "sid", "auth", "ticket", "passport", "uid")


async def _auth_snapshot(ctx):
    """只取与登录相关的 cookie，避免页面自身的埋点 cookie 造成误判。"""
    out = {}
    for c in await ctx.cookies():
        name = (c.get("name") or "").lower()
        if any(h in name for h in AUTH_HINTS):
            out[f"{c.get('domain','')}:{c.get('name','')}"] = c.get("value") or ""
    return out


def main():
    ap = argparse.ArgumentParser(description="登录态浏览器抓页面")
    ap.add_argument("url", help="页面地址")
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE),
                    help=f"浏览器用户目录，默认 {DEFAULT_PROFILE}")
    ap.add_argument("--login", action="store_true", help="有头打开，登录后回车保存登录态")
    ap.add_argument("--login-auto", type=float, default=0, metavar="SEC",
                    help="配合 --login：不用按回车，检测到登录 cookie 变化就自动保存并关闭，最多等 SEC 秒")
    ap.add_argument("--headed", action="store_true", help="有头运行，看得见窗口")
    ap.add_argument("--wait", type=float, default=6, help="首屏等待秒数，默认 6")
    ap.add_argument("--scroll", type=int, default=0, help="向下滚动次数，每次 3000px")
    ap.add_argument("--until", default="domcontentloaded",
                    choices=["load", "domcontentloaded", "networkidle"])
    ap.add_argument("--text", action="store_true", help="整页文字（默认就是它）")
    ap.add_argument("--selector", help="CSS 选择器，取匹配元素的文本")
    ap.add_argument("--attr", help="配合 --selector，取属性而非文本")
    ap.add_argument("--xhr", help="只记录 URL 含该子串的响应")
    ap.add_argument("--xhr-list", help="只列 URL 不取响应体，用来先看这页调了哪些接口")
    ap.add_argument("--xhr-parse", action="store_true", help="把响应体按 JSON 解析")
    ap.add_argument("--js", help="在页面里执行表达式并返回结果")
    ap.add_argument("--shot", help="截图路径")
    ap.add_argument("--fast", nargs="?", const=15, type=float,
                    help="先不开浏览器直接抓正文，可选超时秒数（默认 15），失败自动降级")
    ap.add_argument("--fast-whole", action="store_true",
                    help="--fast 时跳过正文提取，直接要整页文字（列表页/首页用这个）")
    ap.add_argument("--pages", type=int, default=1, help="抓几页，默认 1")
    ap.add_argument("--next", help="翻页元素选择器；不给则用滚动加载")
    ap.add_argument("--page-param", help="URL 翻页参数名（如 page），比点按钮稳")
    ap.add_argument("--page-start", type=int, default=2, help="--page-param 时第二页的编号，默认 2")
    ap.add_argument("--dedupe", help="去重字段名；不给则按整条内容去重")
    ap.add_argument("--seen", help="跨次去重基准文件（JSON 数组），跑完自动更新")
    ap.add_argument("--only-new", action="store_true", help="配合 --seen，只输出本次新增")
    ap.add_argument("--ua", help="覆盖 User-Agent（抖音域名下会被拒绝）")
    ap.add_argument("--json", action="store_true", help="强制 JSON 输出")
    ap.add_argument("--out", help="写入文件而不是打印")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
