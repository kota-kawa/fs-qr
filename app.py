import asyncio
import inspect
import logging
import os
import log_config  # Initialize logging configuration  # noqa: F401
from datetime import date

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starsessions import SessionMiddleware

try:
    from starsessions import SessionAutoloadMiddleware
except ImportError:  # pragma: no cover - fallback for older starsessions
    SessionAutoloadMiddleware = None
from starsessions.stores.redis import RedisStore
from starlette.responses import FileResponse, RedirectResponse, Response

try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
except ImportError:  # pragma: no cover - fallback for older Starlette
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from database import db_session
from migration_runner import run_migrations
from settings import (
    ADMIN_KEY,
    ALLOW_START_WITHOUT_DB,
    BASE_DIR,
    SECRET_KEY,
    REDIS_URL,
    SESSION_MAX_AGE_SECONDS,
)
from web import render_template, wants_json_response
from api_response import api_error_response

from Group.group_app import router as group_router
from Note.note_app import router as note_router
from Note.note_api import router as note_api_router
from Note.note_realtime import shutdown as note_realtime_shutdown
from Note.note_realtime import startup as note_realtime_startup
from Note.note_ws import router as note_ws_router
from Admin.db_admin import router as db_admin_router
from Admin.admin_app import router as admin_router
from FSQR.fsqr_app import router as fsqr_router
from Articles.articles_app import router as articles_router
from top_search import router as top_search_router

MASTER_PW = ADMIN_KEY

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")


def _build_session_middleware_kwargs():
    # starsessions has breaking changes across versions, so pass only supported kwargs.
    params = inspect.signature(SessionMiddleware.__init__).parameters
    kwargs = {"store": RedisStore(REDIS_URL)}

    if "secret_key" in params:
        kwargs["secret_key"] = SECRET_KEY
    if "same_site" in params:
        kwargs["same_site"] = "strict"
    elif "cookie_same_site" in params:
        kwargs["cookie_same_site"] = "strict"
    if "max_age" in params:
        kwargs["max_age"] = SESSION_MAX_AGE_SECONDS
    elif "cookie_max_age" in params:
        kwargs["cookie_max_age"] = SESSION_MAX_AGE_SECONDS
    if "https_only" in params:
        kwargs["https_only"] = True
    elif "cookie_https_only" in params:
        kwargs["cookie_https_only"] = True

    return kwargs


if SessionAutoloadMiddleware is not None:
    # SessionMiddleware must run before autoload so session_handler is available.
    app.add_middleware(SessionAutoloadMiddleware)
app.add_middleware(SessionMiddleware, **_build_session_middleware_kwargs())

app.mount(
    "/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static"
)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    finally:
        await db_session.remove()


@app.on_event("startup")
async def startup():
    ready = False
    for attempt in range(5):
        try:
            await run_migrations()
            ready = True
            break
        except Exception as exc:
            wait_s = min(1.0 * (2**attempt), 10.0)
            logger.warning(
                "Database not ready, retrying startup (%s/5): %s", attempt + 1, exc
            )
            await asyncio.sleep(wait_s)
    if not ready:
        message = (
            "Database startup checks failed after retries; refusing to start web app."
        )
        if ALLOW_START_WITHOUT_DB:
            logger.error("%s ALLOW_START_WITHOUT_DB=true, continuing.", message)
        else:
            logger.critical(message)
            raise RuntimeError(message)
    await note_realtime_startup()
    await db_session.remove()


@app.on_event("shutdown")
async def shutdown():
    await note_realtime_shutdown()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        generic_message = "Resource not found"
        accept = request.headers.get("accept", "")
        if request.url.path.startswith("/api") or "application/json" in accept:
            return api_error_response(generic_message, status_code=exc.status_code)
        if "text/html" in accept or "*/*" in accept:
            response = render_template(request, "404.html")
            response.status_code = 404
            return response
        return api_error_response(generic_message, status_code=exc.status_code)
    return api_error_response(str(exc.detail), status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error during %s %s", request.method, request.url.path)
    if request.url.path.startswith("/api") or wants_json_response(request):
        return api_error_response(
            "サーバーでエラーが発生しました。時間をおいて再度お試しください。",
            status_code=500,
        )
    response = render_template(
        request,
        "error.html",
        message="サーバーでエラーが発生しました。時間をおいて再度お試しください。",
    )
    response.status_code = 500
    return response


app.include_router(group_router)
app.include_router(note_router)
app.include_router(note_api_router)
app.include_router(note_ws_router)
app.include_router(db_admin_router)
app.include_router(admin_router)
app.include_router(fsqr_router)
app.include_router(articles_router)
app.include_router(top_search_router)


def _canonical_redirect(request: Request):
    if request.url.query:
        url = request.url.replace(query="")
        return RedirectResponse(str(url), status_code=301)
    return None


@app.get("/", name="index")
async def index(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "index.html")


@app.get("/privacy-policy", name="privacy_policy")
async def privacy_policy(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "privacy.html")


@app.get("/about", name="about")
async def about(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "about.html")


@app.get("/contact", name="contact")
async def contact(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "contact.html")


@app.get("/usage", name="usage")
async def usage(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "usage.html")


@app.get("/site-operator", name="site_operator")
async def site_operator(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "site_operator.html")


@app.get("/all-in-one", name="all_in_one")
async def all_in_one(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return render_template(request, "all-in-one-gpt.html")


@app.get("/ads.txt", name="ads_txt")
async def ads_txt():
    return FileResponse(os.path.join(BASE_DIR, "ads.txt"))


@app.get("/sitemap.xml", name="sitemap")
async def sitemap():
    # lastmod は該当ページのテンプレート/コードを最後に変更した日付に合わせて更新する
    urls = [
        ("/",                "weekly",  "1.0",  "2026-04-27"),
        ("/about",           "monthly", "0.8",  "2026-04-26"),
        ("/contact",         "monthly", "0.7",  "2026-04-26"),
        ("/usage",           "monthly", "0.8",  "2026-04-26"),
        ("/privacy-policy",  "monthly", "0.6",  "2026-04-26"),
        ("/site-operator",   "monthly", "0.5",  "2026-04-26"),
        ("/articles",        "monthly", "0.8",  "2025-08-31"),
        ("/fs-qr_menu",      "weekly",  "0.9",  "2026-04-27"),
        ("/fs-qr",           "weekly",  "0.9",  "2026-04-27"),
        ("/group_menu",      "weekly",  "0.9",  "2026-04-27"),
        ("/group",           "weekly",  "0.9",  "2026-04-27"),
        ("/create_room",     "weekly",  "0.8",  "2026-04-27"),
        ("/note_menu",       "weekly",  "0.9",  "2026-04-27"),
        ("/note",            "weekly",  "0.9",  "2026-04-27"),
        ("/create_note_room","weekly",  "0.8",  "2026-04-27"),
        ("/fs-qr-concept",   "monthly", "0.6",  "2025-08-31"),
        ("/safe-sharing",    "monthly", "0.6",  "2025-08-31"),
        ("/encryption",      "monthly", "0.6",  "2025-08-21"),
        ("/education",       "monthly", "0.6",  "2025-08-21"),
        ("/business",        "monthly", "0.6",  "2025-08-21"),
        ("/risk-mitigation", "monthly", "0.6",  "2025-08-21"),
    ]
    entries = "\n".join(
        f"  <url><loc>https://fs-qr.com{path}</loc><lastmod>{lastmod}</lastmod>"
        f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        for path, changefreq, priority, lastmod in urls
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")


@app.get("/robots.txt", name="robots")
async def robots():
    return FileResponse(os.path.join(BASE_DIR, "robots.txt"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
