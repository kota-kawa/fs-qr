import asyncio
import logging
import os
import redis.asyncio as redis

import log_config  # Initialize logging configuration

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starsessions import SessionMiddleware
from starsessions.stores.redis import RedisStore
from starlette.responses import FileResponse, JSONResponse, RedirectResponse

try:
    from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
except ImportError:  # pragma: no cover - fallback for older Starlette
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from database import db_session
from Note import note_data
from settings import ADMIN_KEY, BASE_DIR, SECRET_KEY, REDIS_URL
from web import render_template

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

MASTER_PW = ADMIN_KEY

logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(
    SessionMiddleware,
    store=RedisStore(REDIS_URL),
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=True,
)

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


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
            await note_data.ensure_tables()
            ready = True
            break
        except Exception as exc:
            wait_s = min(1.0 * (2**attempt), 10.0)
            logger.warning("Database not ready, retrying startup (%s/5): %s", attempt + 1, exc)
            await asyncio.sleep(wait_s)
    if not ready:
        logger.error("Database startup checks failed after retries; continuing without bootstrap.")
    await note_realtime_startup()
    await db_session.remove()


@app.on_event("shutdown")
async def shutdown():
    await note_realtime_shutdown()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        accept = request.headers.get("accept", "")
        if request.url.path.startswith("/api") or "application/json" in accept:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        if "text/html" in accept or "*/*" in accept:
            response = render_template(request, "404.html")
            response.status_code = 404
            return response
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


app.include_router(group_router)
app.include_router(note_router)
app.include_router(note_api_router)
app.include_router(note_ws_router)
app.include_router(db_admin_router)
app.include_router(admin_router)
app.include_router(fsqr_router)
app.include_router(articles_router)


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
    return FileResponse(os.path.join(BASE_DIR, "sitemap.xml"))


@app.get("/robots.txt", name="robots")
async def robots():
    return FileResponse(os.path.join(BASE_DIR, "robots.txt"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
