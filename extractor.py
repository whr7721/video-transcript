"""Read-only integration with the user's existing MediaCrawler client.

Run with its existing Python environment (-B), never main.py. MediaCrawler's
non-commercial learning license continues to apply to its imported modules.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from batch_rules import classify_post

ROOT = Path(__file__).resolve().parent
MC = Path(r"D:\zcode1\mediacrawler")
PROFILE = Path(os.environ.get("SHIWEN_DATA_DIR", ROOT / "data")).resolve() / "browser"


async def run(action, video_id, sec_uid="", output=None, limit=10, max_duration_sec=600):
    from playwright.async_api import async_playwright
    import httpx

    # Imported code reads libs/douyin.js relative to cwd. It never writes data
    # because we call only its client, not crawler/store/main entrypoints.
    os.chdir(MC)
    sys.path.insert(0, str(MC))
    import media_platform.douyin.client as module

    module.make_async_client = lambda **kwargs: httpx.AsyncClient(trust_env=False, **kwargs)
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(PROFILE), headless=action != "login",
            args=["--no-proxy-server", "--disable-background-networking"],
            viewport={"width": 1360, "height": 900}, locale="zh-CN",
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            if action == "login":
                print(json.dumps({"status": "login_open"}), flush=True)
                await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=45000)
                for _ in range(600):
                    if page.is_closed():
                        break
                    await asyncio.sleep(1)
                return {"status": "login_closed"}

            async def make_client():
                cookies = await context.cookies(["https://www.douyin.com", "https://douyin.com", "https://creator.douyin.com"])
                cookie_dict = {c["name"]: c["value"] for c in cookies}
                ua = await page.evaluate("navigator.userAgent")
                return module.DouYinClient(
                    timeout=35, proxy=None, playwright_page=page, cookie_dict=cookie_dict,
                    headers={"User-Agent": ua, "Referer": "https://www.douyin.com/", "Origin": "https://www.douyin.com",
                             "Accept": "application/json, text/plain, */*",
                             "Cookie": "; ".join(f"{k}={v}" for k, v in cookie_dict.items())})

            if action == "creator":
                from media_platform.douyin.media import extract_video_urls
                checkpoint = json.loads(Path(output).read_text(encoding="utf-8")) if Path(output).exists() else {}
                checkpoint = checkpoint if checkpoint.get("sec_uid") == sec_uid else {}
                posts = checkpoint.get("posts", [])
                seen = {str(p.get("aweme_id")) for p in posts}
                cursor = checkpoint.get("cursor", "")
                page_cursors = set(checkpoint.get("page_cursors", []))

                def persist(**fields):
                    checkpoint.update(fields, sec_uid=sec_uid, posts=posts, cursor=cursor, page_cursors=list(page_cursors))
                    checkpoint["sources"] = {str(p.get("aweme_id")): extract_video_urls(p) for p in posts if isinstance(p.get("video"), dict)}
                    destination = Path(output)
                    temporary = destination.with_suffix(".tmp")
                    temporary.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
                    temporary.replace(destination)

                if checkpoint.get("scan_complete"):
                    return checkpoint
                try:
                    await page.goto(f"https://www.douyin.com/user/{sec_uid}", wait_until="domcontentloaded", timeout=40000)
                except Exception:
                    pass
                await asyncio.sleep(3)
                client = await make_client()
                try:
                    profile = await client.get_user_info(sec_uid)
                    user = profile.get("user", {})
                    persist(author=user.get("nickname") or checkpoint.get("author", ""), status="collecting")
                except Exception:
                    persist(status="collecting")
                while sum(classify_post(p, max_duration_sec)[0] in {"eligible", "unknown"} for p in posts) < limit:
                    response = None
                    for attempt in range(3):
                        try:
                            response = await client.get_user_aweme_posts(sec_uid, cursor)
                            if not isinstance(response, dict) or "has_more" not in response or response.get("status_code", 0) != 0:
                                raise RuntimeError("主页接口没有返回有效分页信息")
                            break
                        except Exception:
                            if attempt == 2:
                                persist(status="error", error="主页列表获取失败，已保存分页进度。请检查登录后重试。")
                                return checkpoint
                            await asyncio.sleep(2 + attempt * 2)
                    page_items = response.get("aweme_list") or []
                    if not isinstance(page_items, list):
                        persist(status="error", error="主页列表格式异常，未将其当作空主页。")
                        return checkpoint
                    before = len(posts)
                    for post in page_items:
                        ident = str(post.get("aweme_id", ""))
                        author_id = post.get("author", {}).get("sec_uid")
                        if ident not in seen and (not author_id or author_id == sec_uid):
                            seen.add(ident)
                            posts.append(post)
                    next_cursor = str(response.get("max_cursor", ""))
                    has_more = bool(response.get("has_more"))
                    page_cursors.add(str(cursor))
                    cursor = next_cursor
                    persist(has_more=has_more, pages=checkpoint.get("pages", 0)+1)
                    if not has_more:
                        persist(status="ok", stop_reason="end", scan_complete=True)
                        return checkpoint
                    if next_cursor in page_cursors or len(posts) == before:
                        persist(status="error", error="主页分页未继续前进，已保存已获取作品，未假定全部采集完成。")
                        return checkpoint
                    if checkpoint.get("pages", 0) >= 100:
                        persist(status="ok", stop_reason="page_limit", scan_complete=False)
                        return checkpoint
                    await asyncio.sleep(2)
                persist(status="ok", stop_reason="batch_limit", scan_complete=False)
                return checkpoint

            details = []

            async def on_response(response):
                if "/aweme/v1/web/aweme/detail/" in response.url and response.status == 200:
                    try:
                        result = await response.json()
                        item = result.get("aweme_detail")
                        if item and str(item.get("aweme_id")) == video_id:
                            details.append(item)
                    except Exception:
                        pass

            page.on("response", on_response)
            try:
                await page.goto(f"https://www.douyin.com/{'note' if action == 'images' else 'video'}/{video_id}",
                                wait_until="domcontentloaded", timeout=45000)
            except Exception:
                pass  # A page timeout doesn't imply its authenticated API failed.
            for _ in range(12):
                if details:
                    break
                await asyncio.sleep(1)
            if details:
                item = details[-1]
            else:
                cookies = await context.cookies(["https://www.douyin.com", "https://douyin.com", "https://creator.douyin.com"])
                cookie_dict = {c["name"]: c["value"] for c in cookies}
                ua = await page.evaluate("navigator.userAgent")
                client = module.DouYinClient(
                    timeout=35, proxy=None, playwright_page=page, cookie_dict=cookie_dict,
                    headers={"User-Agent": ua, "Referer": "https://www.douyin.com/",
                             "Origin": "https://www.douyin.com",
                             "Accept": "application/json, text/plain, */*",
                             "Cookie": "; ".join(f"{k}={v}" for k, v in cookie_dict.items())},
                )
                try:
                    item = await client.get_video_by_id(video_id)
                except Exception as exc:
                    # Do not leak request/cookie headers or response bodies.
                    raise RuntimeError(f"抖音详情获取失败（{type(exc).__name__}），请检查登录状态后重试。") from None
            if not item or str(item.get("aweme_id")) != video_id:
                raise RuntimeError("未取得该作品详情。请检查视频是否可访问，或重新登录抖音。")
            if action == 'images':
                images = item.get('images') or []
                if not isinstance(images, list) or not images:
                    raise RuntimeError('该作品未返回图集图片，请确认是图文作品。')
                return {'status':'ok','id':video_id,'title':item.get('desc',''),
                        'author':item.get('author',{}).get('nickname',''),
                        'images':[{'index':i,'urls':[u for u in (image.get('url_list') or []) if isinstance(u,str)]}
                                  for i,image in enumerate(images)],'total':len(images)}
            from media_platform.douyin.media import extract_video_urls
            urls = extract_video_urls(item)
            if not urls:
                raise RuntimeError("作品没有可用的视频音轨；图文作品暂不支持。")
            return {"status": "ok", "detail": item, "urls": urls}
        finally:
            await context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["extract", "images", "login", "creator"])
    parser.add_argument("--id", default="")
    parser.add_argument("--sec-uid", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-duration-sec", type=int, choices=[600, 1200, 1800], default=600)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    args.output = str(Path(args.output).resolve())
    if args.action in {"extract", "images"} and not re.fullmatch(r"\d{15,22}", args.id):
        sys.exit("无效作品 ID")
    if args.action == "creator" and (not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", args.sec_uid) or not 1 <= args.limit <= 100):
        sys.exit("无效博主 ID 或批次数量")
    try:
        result = asyncio.run(run(args.action, args.id, args.sec_uid, args.output, args.limit, args.max_duration_sec))
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"status": result["status"]}), flush=True)
    except Exception as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else f"采集启动失败（{type(exc).__name__}）。"
        failed = {}
        if args.action == "creator" and Path(args.output).exists():
            try:
                failed = json.loads(Path(args.output).read_text(encoding="utf-8"))
            except ValueError:
                pass
        failed.update(status="error", error=message)
        Path(args.output).write_text(json.dumps(failed, ensure_ascii=False), encoding="utf-8")
        print(message, file=sys.stderr)
        sys.exit(1)
