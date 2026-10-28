"""Application assembly shared by the two entry points."""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

async def local_security(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "仅允许从本工具页面提交任务。"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "不允许跨站请求。"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if request.url.path.startswith("/cards/"):
        response.headers["Content-Security-Policy"] = response.headers["Content-Security-Policy"].replace("img-src 'self' data:", "img-src 'self' data: blob:")
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


def install_shared(app):
    import os
    from studio_api import router as studio
    from research_api import router as research
    from article_api import router as articles
    if os.environ.get('SHIWEN_PUBLIC') == '1':
        allowed = [h.strip() for h in os.environ.get('SHIWEN_ALLOWED_HOSTS', '*').split(',') if h.strip()]
    else:
        allowed = ['localhost', '127.0.0.1', 'testserver']
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed)
    app.middleware("http")(local_security)
    for router in (studio, research, articles):
        app.include_router(router)


def recover_shared():
    import store, media_buffer, organizer, research, articles
    store.init()
    media_buffer.migrate_known()
    organizer.recover()
    research.recover()
    articles.recover()
    import chapter_jobs
    chapter_jobs.recover()
