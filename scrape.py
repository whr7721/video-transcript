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
    python scrape.py --login <url>                           # 新建登录态，扫码后回车

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
from pathlib import Path
from urllib.parse import urlsplit

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


def fast_fetch(url, timeout):
    """不开浏览器直接拿正文。返回 (payload, reason)，失败时 payload 为 None。"""
    try:
        from curl_cffi import requests as creq
    except ImportError:
        return None, "curl_cffi 未安装"
    try:
        r = creq.get(url, impersonate="chrome", timeout=timeout, allow_redirects=True)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"[:110]
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"

    html = decode_html(r)
    for mark in CHALLENGE_MARKS:
        if mark in html:
            return None, f"反爬挑战页（{mark}）"

    try:
        import trafilatura
        text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
    except ImportError:                       # 退化成粗暴去标签，聊胜于无
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 200:
        return None, "正文过短（多半是前端渲染页）"

    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    return {"url": url, "title": title, "mode": "fast", "chars": len(text), "data": text}, None


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


async def run(args):
    guard_ua(args.url, args.ua)

    # 只有纯文字模式才走快路径：要选择器 / 要接口 / 要截图，都必须有浏览器。
    pure_text = not (args.selector or args.js or args.xhr or args.xhr_list or args.shot)
    if args.fast and pure_text and not args.login:
        payload, reason = fast_fetch(args.url, args.fast)
        if payload:
            text = json.dumps(payload, ensure_ascii=False, indent=2) if args.json else payload["data"]
            if args.out:
                Path(args.out).write_text(text, encoding="utf-8")
                print(f"写入 {Path(args.out).resolve()}", file=sys.stderr)
            else:
                sys.stdout.reconfigure(encoding="utf-8")
                print(text)
            print(f"[fast] {payload['chars']} 字，{payload['title'][:40]}", file=sys.stderr)
            return 0
        print(f"[fast] 降级到浏览器：{reason}", file=sys.stderr)

    from playwright.async_api import async_playwright

    profile = Path(args.profile).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    captured = []
    hits = [0]

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
            elif args.js:
                data = await page.evaluate(args.js)
            elif args.selector:
                data = await page.evaluate(PICK, [args.selector, args.attr])
            else:
                data = await page.evaluate("document.body.innerText")

            title = await page.title()
            if args.shot:
                await page.screenshot(path=args.shot, full_page=False)
                print(f"截图 {Path(args.shot).resolve()}", file=sys.stderr)
        finally:
            await ctx.close()

    if isinstance(data, list):
        mode = "xhr" if (args.xhr or args.xhr_list) else ("js" if args.js else "selector")
        envelope = {"url": args.url, "title": title, "mode": mode,
                    "count": len(data), "data": data}
    else:
        envelope = {"url": args.url, "title": title, "mode": "text", "data": data}

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


def main():
    ap = argparse.ArgumentParser(description="登录态浏览器抓页面")
    ap.add_argument("url", help="页面地址")
    ap.add_argument("--profile", default=str(DEFAULT_PROFILE),
                    help=f"浏览器用户目录，默认 {DEFAULT_PROFILE}")
    ap.add_argument("--login", action="store_true", help="有头打开，登录后回车保存登录态")
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
    ap.add_argument("--ua", help="覆盖 User-Agent（抖音域名下会被拒绝）")
    ap.add_argument("--json", action="store_true", help="强制 JSON 输出")
    ap.add_argument("--out", help="写入文件而不是打印")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
