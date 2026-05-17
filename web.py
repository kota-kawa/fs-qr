import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any, Dict, Iterable
from urllib.parse import quote_plus

from fastapi import HTTPException, Request, WebSocket
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.responses import HTMLResponse

from cache_utils import redis_client
from i18n import (
    get_language_options,
    get_frontend_messages,
    make_translator,
    resolve_language,
    translate_rendered_html,
)

from settings import (
    BASE_DIR,
    FRONTEND_DEBUG,
    GROUP_FILE_LIST_POLL_INTERVAL_MS,
    GROUP_FILE_LIST_REQUEST_TIMEOUT_MS,
    NOTE_MAX_CONTENT_LENGTH,
    NOTE_SELF_EDIT_TIMEOUT_MS,
    UPLOAD_MAX_FILES,
    UPLOAD_MAX_TOTAL_SIZE_BYTES,
    UPLOAD_MAX_TOTAL_SIZE_MB,
)

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
ASYNC_REQUEST_HEADER = "x-requested-with"


class TemplateRequestProxy:
    SUPPORTED_HREFLANG_LANGS = ("ja", "en", "zh-CN")

    def __init__(self, request: Request) -> None:
        self._request = request

    @property
    def url_root(self) -> str:
        url = self._request.url
        return str(url.replace(path="/", query=""))

    def _current_lang_param(self) -> str:
        raw = self._request.query_params.get("lang", "").strip()
        # 大文字小文字を正規化（zh-cn → zh-CN）
        if raw.lower() == "zh-cn":
            return "zh-CN"
        if raw in self.SUPPORTED_HREFLANG_LANGS:
            return raw
        return ""

    @property
    def canonical_url(self) -> str:
        url = self._request.url
        lang = self._current_lang_param()
        if lang:
            return str(url.replace(query=f"lang={lang}"))
        return str(url.replace(query=""))

    @property
    def language_alternates(self) -> list[dict[str, str]]:
        """hreflang 用の各言語版URLを返す。

        - 既定言語 (ja) は ?lang= なし
        - その他は ?lang=<code>
        - x-default は ja と同じURL
        """
        base = str(self._request.url.replace(query=""))
        alternates: list[dict[str, str]] = []
        for code in self.SUPPORTED_HREFLANG_LANGS:
            if code == "ja":
                href = base
            else:
                href = f"{base}?lang={code}"
            alternates.append({"hreflang": code, "href": href})
        alternates.append({"hreflang": "x-default", "href": base})
        return alternates

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


def wants_json_response(request: Request) -> bool:
    requested_with = request.headers.get(ASYNC_REQUEST_HEADER, "").lower()
    if requested_with in {"fetch", "xmlhttprequest"}:
        return True

    accept = request.headers.get("accept", "").lower()
    return "application/json" in accept and "text/html" not in accept


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


def _extract_websocket_csrf_token(websocket: WebSocket) -> str:
    query_params = getattr(websocket, "query_params", None)
    if hasattr(query_params, "get"):
        query_token = _normalize_csrf_token(query_params.get(CSRF_FORM_FIELD))
        if query_token:
            return query_token

    headers = getattr(websocket, "headers", None)
    if hasattr(headers, "get"):
        header_token = _normalize_csrf_token(headers.get(CSRF_HEADER_NAME))
        if header_token:
            return header_token

    return ""


def _get_websocket_session(websocket: WebSocket) -> Any:
    session = getattr(websocket, "session", None)
    if session is not None:
        return session

    scope = getattr(websocket, "scope", None)
    if isinstance(scope, dict):
        return scope.get("session")
    return None


def validate_websocket_csrf(websocket: WebSocket) -> bool:
    provided = _extract_websocket_csrf_token(websocket)
    if not provided:
        return False

    session = _get_websocket_session(websocket)
    if session is None or not hasattr(session, "get"):
        return False

    expected = _normalize_csrf_token(session.get(CSRF_SESSION_KEY))
    if not expected:
        return False

    return hmac.compare_digest(provided, expected)


@pass_context
def csrf_token(context: Dict[str, Any]) -> str:
    request: Request = context.get("request")
    if request is None:
        return ""
    return get_or_create_csrf_token(request)


logger = logging.getLogger(__name__)


def render_template(request: Request, template_name: str, **context: Any):
    language = resolve_language(request)
    payload = {
        "request": TemplateRequestProxy(request),
        "current_language": language,
        "language_options": get_language_options(language),
        "frontend_messages": get_frontend_messages(language),
        "t": make_translator(language),
    }
    payload.update(context)
    try:
        template = templates.env.get_template(template_name)
        content = template.render(payload)
        content = translate_rendered_html(content, language)
        return HTMLResponse(
            content,
            headers={
                "Vary": "Cookie",
                "Content-Language": language,
            },
        )
    except Exception as e:
        logger.exception(f"Error rendering template {template_name}: {e}")
        raise e


RENDER_CACHE_KEY_PREFIX = "render_cache"
RENDER_CACHE_CSRF_PLACEHOLDER = "__FSQR_CSRF_TOKEN_PLACEHOLDER__"


def _render_cache_key(template_name: str, language: str, request: Request) -> str:
    # ?lang= の有無で canonical_url が変わるため、クエリの生値もキーに含める
    raw_lang = ""
    qp = getattr(request, "query_params", None)
    if qp is not None:
        raw_lang = (qp.get("lang") or "").strip().lower()
    payload = f"{template_name}|{language}|{raw_lang}|{int(bool(FRONTEND_DEBUG))}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{RENDER_CACHE_KEY_PREFIX}:{digest}"


async def render_cached_template(
    request: Request,
    template_name: str,
    *,
    ttl: int = 300,
    **context: Any,
):
    """フォーム送信を伴わない静的ページ向けのキャッシュ付きレンダラ。

    レンダリング結果（多言語変換後の HTML）を Redis に保存し、再リクエスト時の
    Jinja2 レンダ＋多言語置換（数百フレーズ）を省略する。

    セッション依存の CSRF トークンはプレースホルダに置換して保存し、配信時に
    リクエスト毎のトークンへ差し替える。``context`` を渡した呼び出しは
    動的データを含む可能性があるためキャッシュをバイパスする。
    """
    if context:
        return render_template(request, template_name, **context)

    language = resolve_language(request)
    cache_key = _render_cache_key(template_name, language, request)
    csrf_value = get_or_create_csrf_token(request)

    cached_body: str | None = None
    try:
        cached_body = await redis_client.get(cache_key)
    except Exception as exc:
        logger.warning("Render cache GET failed (%s): %s", cache_key, exc)

    if cached_body is not None:
        body = cached_body.replace(RENDER_CACHE_CSRF_PLACEHOLDER, csrf_value)
        return HTMLResponse(
            body,
            headers={
                "Vary": "Cookie",
                "Content-Language": language,
                "X-Render-Cache": "HIT",
            },
        )

    response = render_template(request, template_name)
    body = response.body.decode("utf-8")

    if csrf_value and RENDER_CACHE_CSRF_PLACEHOLDER not in body:
        cacheable_body = body.replace(csrf_value, RENDER_CACHE_CSRF_PLACEHOLDER)
        try:
            await redis_client.setex(cache_key, ttl, cacheable_body)
        except Exception as exc:
            logger.warning("Render cache SETEX failed (%s): %s", cache_key, exc)

    response.headers["X-Render-Cache"] = "MISS"
    return response


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
    upload_max_files=UPLOAD_MAX_FILES,
    upload_max_total_size_mb=UPLOAD_MAX_TOTAL_SIZE_MB,
    upload_max_total_size_bytes=UPLOAD_MAX_TOTAL_SIZE_BYTES,
    note_max_content_length=NOTE_MAX_CONTENT_LENGTH,
    note_self_edit_timeout_ms=NOTE_SELF_EDIT_TIMEOUT_MS,
    group_file_list_poll_interval_ms=GROUP_FILE_LIST_POLL_INTERVAL_MS,
    group_file_list_request_timeout_ms=GROUP_FILE_LIST_REQUEST_TIMEOUT_MS,
)
