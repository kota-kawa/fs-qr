import hmac
import logging
import os
import secrets
import time
from typing import Any, Dict, Iterable
from urllib.parse import quote_plus

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from settings import BASE_DIR, FRONTEND_DEBUG

TEMPLATE_DIRS = [
    os.path.join(BASE_DIR, "templates"),
    os.path.join(BASE_DIR, "FSQR", "templates"),
    os.path.join(BASE_DIR, "Group", "templates"),
    os.path.join(BASE_DIR, "Note", "templates"),
    os.path.join(BASE_DIR, "Admin", "templates"),
    os.path.join(BASE_DIR, "Articles", "templates"),
]

# Filter out missing directories to avoid loader warnings.
TEMPLATE_DIRS = [path for path in TEMPLATE_DIRS if os.path.isdir(path)]

templates = Jinja2Templates(directory=TEMPLATE_DIRS)

CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class TemplateRequestProxy:
    def __init__(self, request: Request) -> None:
        self._request = request

    @property
    def url_root(self) -> str:
        url = self._request.url
        return str(url.replace(path="/", query=""))

    def __getattr__(self, name: str):
        return getattr(self._request, name)


def staticfile(fname: str) -> str:
    path = os.path.join(BASE_DIR, "static", fname)
    if os.path.exists(path):
        mtime = str(int(os.stat(path).st_mtime))
        return "/static/" + fname + "?v=" + str(mtime)
    return "/static/" + fname


@pass_context
def url_for(context: Dict[str, Any], name: str, **params: Any) -> str:
    request: Request = context.get("request")
    if request is None:
        return ""
    external = bool(params.pop("_external", False))
    url = request.url_for(name, **params)
    if external:
        return str(url)
    return url.path


@pass_context
def get_flashed_messages(context: Dict[str, Any]) -> Iterable[str]:
    request: Request = context.get("request")
    if request is None:
        return []
    messages = request.session.pop("_flashes", [])
    if not isinstance(messages, list):
        return []
    return messages


def flash_message(request: Request, message: str) -> None:
    messages = request.session.get("_flashes")
    if not isinstance(messages, list):
        messages = []
    messages.append(message)
    request.session["_flashes"] = messages


def _normalize_csrf_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip()
    return token


def get_or_create_csrf_token(request: Request) -> str:
    token = _normalize_csrf_token(request.session.get(CSRF_SESSION_KEY))
    if token:
        return token
    token = secrets.token_urlsafe(32)
    request.session[CSRF_SESSION_KEY] = token
    return token


async def _extract_csrf_token(request: Request) -> str:
    header_token = _normalize_csrf_token(request.headers.get(CSRF_HEADER_NAME))
    if header_token:
        return header_token

    content_type = request.headers.get("content-type", "")
    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        form = await request.form()
        form_token = _normalize_csrf_token(form.get(CSRF_FORM_FIELD))
        if form_token:
            return form_token

    return ""


async def validate_csrf(request: Request) -> bool:
    expected = get_or_create_csrf_token(request)
    provided = await _extract_csrf_token(request)
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


async def enforce_csrf(request: Request) -> None:
    if request.method in SAFE_HTTP_METHODS:
        return
    if await validate_csrf(request):
        return
    raise HTTPException(status_code=403, detail="CSRF token missing or invalid")


@pass_context
def csrf_token(context: Dict[str, Any]) -> str:
    request: Request = context.get("request")
    if request is None:
        return ""
    return get_or_create_csrf_token(request)


logger = logging.getLogger(__name__)


def render_template(request: Request, template_name: str, **context: Any):
    payload = {"request": TemplateRequestProxy(request)}
    payload.update(context)
    try:
        return templates.TemplateResponse(template_name, payload)
    except Exception as e:
        logger.exception(f"Error rendering template {template_name}: {e}")
        raise e


def build_url(request: Request, name: str, **params: Any) -> str:
    external = bool(params.pop("_external", False))
    url = request.url_for(name, **params)
    if external:
        return str(url)
    return url.path


def _filter_datetime(tm: float) -> str:
    return time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(tm))


def _filter_urlencode(value: Any) -> str:
    return quote_plus(str(value))


templates.env.filters["datetime"] = _filter_datetime
# Provide a safe urlencode filter even if not present.
templates.env.filters.setdefault("urlencode", _filter_urlencode)

templates.env.globals.update(
    staticfile=staticfile,
    url_for=url_for,
    get_flashed_messages=get_flashed_messages,
    csrf_token=csrf_token,
    frontend_debug=FRONTEND_DEBUG,
)
