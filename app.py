import asyncio
import contextlib
import inspect
import logging
import os
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
import log_config  # Initialize logging configuration  # noqa: F401

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
    GEOIP_AUTO_UPDATE,
    SECRET_KEY,
    REDIS_URL,
    SESSION_MAX_AGE_SECONDS,
    TRUSTED_PROXY_HOSTS,
)
from i18n import is_language_query_only
from security_headers import apply_security_headers
from web import render_cached_template, render_template, wants_json_response
from api_response import api_error_response
from geoip_update import geoip_update_loop, update_geoip_database_async

from Group.group_app import router as group_router
from Note.note_app import router as note_router
from Note.note_api import router as note_api_router
from Note.note_realtime import shutdown as note_realtime_shutdown
from Note.note_realtime import startup as note_realtime_startup
from Note.note_ws import router as note_ws_router
from Admin.db_admin import router as db_admin_router
from Admin.admin_app import router as admin_router
from FSQR import fsqr_data as fsqr_cleanup_data
from FSQR.fsqr_app import router as fsqr_router
from Articles.articles_app import router as articles_router
from Articles.articles_registry import get_all_articles
from top_search import router as top_search_router
from presence_api import router as presence_router

MASTER_PW = ADMIN_KEY

logger = logging.getLogger(__name__)
_geoip_update_stop_event = None
_geoip_update_task = None

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=TRUSTED_PROXY_HOSTS)


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
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    apply_security_headers(response.headers)
    return response


@app.middleware("http")
async def set_locale_middleware(request: Request, call_next):
    from i18n import resolve_language, current_language_ctx

    lang = resolve_language(request)
    token = current_language_ctx.set(lang)
    try:
        response = await call_next(request)
        return response
    finally:
        current_language_ctx.reset(token)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    if request.url.path.startswith("/static/group_uploads"):
        return Response(status_code=404)
    try:
        response = await call_next(request)
        return response
    finally:
        await db_session.remove()


@app.on_event("startup")
async def startup():
    global _geoip_update_stop_event, _geoip_update_task

    if GEOIP_AUTO_UPDATE:
        try:
            await update_geoip_database_async()
        except Exception as exc:
            logger.warning("GeoIP database startup update failed: %s", exc)
        _geoip_update_stop_event = asyncio.Event()
        _geoip_update_task = asyncio.create_task(
            geoip_update_loop(_geoip_update_stop_event)
        )

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
    try:
        fsqr_cleanup_stats = await fsqr_cleanup_data.remove_expired_files()
        logger.info("FSQR startup expiration cleanup completed: %s", fsqr_cleanup_stats)
    except Exception:
        logger.exception("FSQR startup expiration cleanup failed")
    await note_realtime_startup()
    await db_session.remove()


@app.on_event("shutdown")
async def shutdown():
    global _geoip_update_stop_event, _geoip_update_task
    if _geoip_update_stop_event is not None:
        _geoip_update_stop_event.set()
    if _geoip_update_task is not None:
        with contextlib.suppress(asyncio.CancelledError):
            await _geoip_update_task
        _geoip_update_task = None
        _geoip_update_stop_event = None
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
app.include_router(presence_router)


def _canonical_redirect(request: Request):
    # ?lang=<supported> は hreflang 用に許可、それ以外のクエリは正規化のため301
    query = request.url.query
    if not query:
        return None
    if is_language_query_only(request):
        return None
    url = request.url.replace(query="")
    return RedirectResponse(str(url), status_code=301)


@app.get("/", name="index")
async def index(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "index.html")


@app.get("/privacy-policy", name="privacy_policy")
async def privacy_policy(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "privacy.html")


@app.get("/terms", name="terms")
async def terms(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "terms.html")


@app.get("/about", name="about")
async def about(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "about.html")


@app.get("/contact", name="contact")
async def contact(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "contact.html")


@app.get("/usage", name="usage")
async def usage(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "usage.html")


@app.get("/site-operator", name="site_operator")
async def site_operator(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "site_operator.html")


@app.get("/all-in-one", name="all_in_one")
async def all_in_one(request: Request):
    canonical = _canonical_redirect(request)
    if canonical:
        return canonical
    return await render_cached_template(request, "all-in-one-gpt.html")


@app.get("/ads.txt", name="ads_txt")
async def ads_txt():
    return FileResponse(os.path.join(BASE_DIR, "ads.txt"))


SITEMAP_BASE_URL = "https://fs-qr.net"


# lastmod を手動更新する代わりに、各ページのテンプレート最終更新日から自動算出する際の
# 最終フォールバック日（git 履歴も mtime も取得できない場合に使用）。
SITEMAP_FALLBACK_LASTMOD = "2026-04-27"


def _articles_lastmod() -> str:
    return max(
        (article["date"] for article in get_all_articles()), default="2025-08-31"
    )


@lru_cache(maxsize=None)
def _git_commit_date(abs_path: str) -> str | None:
    """指定ファイルを最後に変更した git コミット日 (YYYY-MM-DD) を返す。

    .git が無い本番イメージ等では取得できないため、その場合は None を返し
    呼び出し側で mtime にフォールバックする。
    """
    try:
        # 引数はすべてサーバ側で固定（ユーザー入力なし）のため安全。git が PATH に
        # 無い／.git が存在しない環境では例外になり、呼び出し側が mtime へフォールバックする。
        result = subprocess.run(  # noqa: S603
            ["git", "-C", BASE_DIR, "log", "-1", "--format=%cs", "--", abs_path],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    out = result.stdout.strip()
    return out or None


@lru_cache(maxsize=None)
def _template_lastmod(*rel_paths: str) -> str:
    """列挙したテンプレートの最終更新日 (YYYY-MM-DD) の最大値を返す。

    git コミット日を優先し、取得できなければファイル mtime にフォールバックする。
    これによりテンプレートを編集すれば <lastmod> が自動で追従し、手動更新漏れを防ぐ。
    """
    dates: list[str] = []
    for rel in rel_paths:
        abs_path = os.path.join(BASE_DIR, rel)
        if not os.path.exists(abs_path):
            continue
        date = _git_commit_date(abs_path) or datetime.fromtimestamp(
            os.path.getmtime(abs_path), tz=timezone.utc
        ).strftime("%Y-%m-%d")
        dates.append(date)
    return max(dates) if dates else SITEMAP_FALLBACK_LASTMOD


# 各ページの sitemap 設定: (path, changefreq, priority, lastmod 算出に使うテンプレート…)。
# lastmod は列挙したテンプレートの最終更新日から自動算出する（_template_lastmod 参照）。
SITEMAP_PAGES = (
    ("/", "weekly", "1.0", ("templates/index.html",)),
    ("/about", "monthly", "0.8", ("templates/about.html", "templates/layout.html")),
    ("/contact", "monthly", "0.7", ("templates/contact.html", "templates/layout.html")),
    ("/usage", "monthly", "0.8", ("templates/usage.html", "templates/layout.html")),
    (
        "/privacy-policy",
        "monthly",
        "0.6",
        ("templates/privacy.html", "templates/layout.html"),
    ),
    ("/terms", "monthly", "0.6", ("templates/terms.html", "templates/layout.html")),
    (
        "/site-operator",
        "monthly",
        "0.5",
        ("templates/site_operator.html", "templates/layout.html"),
    ),
    ("/articles", "monthly", "0.8", ("Articles/templates/articles.html",)),
    ("/fs-qr_menu", "weekly", "0.9", ("FSQR/templates/fs-qr.html",)),
    (
        "/fs-qr",
        "weekly",
        "0.9",
        ("FSQR/templates/fs-qr-upload.html", "templates/layout.html"),
    ),
    ("/group_menu", "weekly", "0.9", ("Group/templates/group.html",)),
    (
        "/group",
        "weekly",
        "0.9",
        ("Group/templates/group_room_access.html", "templates/group_layout.html"),
    ),
    (
        "/create_room",
        "weekly",
        "0.8",
        ("Group/templates/create_group_room.html", "templates/group_layout.html"),
    ),
    ("/note_menu", "weekly", "0.9", ("Note/templates/note_menu.html",)),
    (
        "/note",
        "weekly",
        "0.9",
        ("Note/templates/note_room_access.html", "Note/templates/note_layout.html"),
    ),
    (
        "/create_note_room",
        "weekly",
        "0.8",
        ("Note/templates/create_note_room.html", "Note/templates/note_layout.html"),
    ),
)


def _build_sitemap_entry(
    path: str, changefreq: str, priority: str, lastmod: str
) -> str:
    loc = f"{SITEMAP_BASE_URL}{path}"
    return (
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{lastmod}</lastmod>\n"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority}</priority>\n"
        "  </url>"
    )


@app.get("/sitemap.xml", name="sitemap")
async def sitemap():
    # lastmod はテンプレートの最終更新日から自動算出する（_template_lastmod 参照）。
    # hreflang は各ページの HTML head で管理し、sitemap は canonical URL の列挙に絞る。
    # NOTE: /all-in-one, /search_fs-qr, /search_group, /search_note は noindex のため除外。
    rows: list[str] = []
    for path, changefreq, priority, templates in SITEMAP_PAGES:
        lastmod = _template_lastmod(*templates)
        # 記事一覧は最新記事の公開日も反映する（新規記事の追加で鮮度を更新）。
        if path == "/articles":
            lastmod = max(lastmod, _articles_lastmod())
        rows.append(_build_sitemap_entry(path, changefreq, priority, lastmod))
    # 解説記事の個別ページはレジストリの公開日を lastmod として自動生成する。
    for article in get_all_articles():
        rows.append(
            _build_sitemap_entry(
                f"/{article['slug']}", "monthly", "0.6", article["date"]
            )
        )
    entries = "\n".join(rows)
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

    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)  # noqa: S104
