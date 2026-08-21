import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any, Dict, Iterable
from urllib.parse import quote_plus, urlsplit, urlunsplit

from fastapi import HTTPException, Request, WebSocket
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.responses import HTMLResponse

from cache_utils import redis_client
from i18n import (
    DEFAULT_LANGUAGE,
    JAPANESE_ONLY_MODE,
    get_language_options,
    get_frontend_messages,
    make_translator,
    normalize_language,
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
    TASK_MAX_TAG_LENGTH,
    TASK_MAX_TAGS_PER_ITEM,
    TASK_MAX_TAGS_PER_ROOM,
    TASK_MAX_ITEMS_PER_ROOM,
    TASK_MAX_NOTE_LENGTH,
    TASK_MAX_TITLE_LENGTH,
    PUBLIC_SITE_URL,
    UPLOAD_MAX_FILES,
    UPLOAD_MAX_TOTAL_SIZE_BYTES,
    UPLOAD_MAX_TOTAL_SIZE_MB,
)

TEMPLATE_DIRS = [
    os.path.join(BASE_DIR, "templates"),
    os.path.join(BASE_DIR, "FSQR", "templates"),
    os.path.join(BASE_DIR, "Group", "templates"),
    os.path.join(BASE_DIR, "Note", "templates"),
    os.path.join(BASE_DIR, "Task", "templates"),
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
    # AdSense 再審査中は日本語 canonical 面だけを検索評価対象にする。
    SUPPORTED_HREFLANG_LANGS = ("ja",)

    def __init__(self, request: Request) -> None:
        self._request = request

    def _absolute_public_url(
        self, *, path: str | None = None, query: str | None = None
    ) -> str:
        url = self._request.url
        resolved_path = path if path is not None else url.path
        resolved_query = url.query if query is None else query

        if PUBLIC_SITE_URL:
            public_base = urlsplit(PUBLIC_SITE_URL)
            return urlunsplit(
                (
                    public_base.scheme or "https",
                    public_base.netloc,
                    resolved_path,
                    resolved_query,
                    "",
                )
            )

        return str(url.replace(path=resolved_path, query=resolved_query))

    @property
    def url_root(self) -> str:
        return self._absolute_public_url(path="/", query="")

    def _current_lang_param(self) -> str:
        raw = self._request.query_params.get("lang", "").strip()
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered.startswith("ja") or lowered.startswith("jp"):
            return "ja"
        normalized = normalize_language(raw)
        if normalized != "ja" and normalized in self.SUPPORTED_HREFLANG_LANGS:
            return normalized
        return ""

    @property
    def canonical_url(self) -> str:
        lang = self._current_lang_param()
        if lang:
            return self._absolute_public_url(query=f"lang={lang}")
        return self._absolute_public_url(query="")

    @property
    def language_alternates(self) -> list[dict[str, str]]:
        """hreflang 用の各言語版URLを返す。

        - 既定言語 (ja) は ?lang= なし
        - その他は ?lang=<code>
        - x-default は ja と同じURL
        """
        base = self._absolute_public_url(query="")
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


def _staticfile_ref(fname: str, *, version: bool) -> tuple[str, str]:
    path = os.path.join(BASE_DIR, "static", fname)
    if version and os.path.exists(path):
        mtime = str(int(os.stat(path).st_mtime))
        return "/static/" + fname, "v=" + str(mtime)
    return "/static/" + fname, ""


def staticfile(fname: str) -> str:
    path, query = _staticfile_ref(fname, version=True)
    if query:
        return path + "?" + query
    return path


@pass_context
def social_staticfile(context: Dict[str, Any], fname: str) -> str:
    """Return an absolute static URL for Open Graph and Twitter Card crawlers."""
    path, query = _staticfile_ref(fname, version=False)
    request = context.get("request")
    if isinstance(request, TemplateRequestProxy):
        return request._absolute_public_url(path=path, query=query)

    public_base = urlsplit(PUBLIC_SITE_URL)
    return urlunsplit(
        (
            public_base.scheme or "https",
            public_base.netloc,
            path,
            query,
            "",
        )
    )


GOOGLE_ANALYTICS_ID = "G-D26D8ZXKNV"
GOOGLE_ADSENSE_CLIENT_ID = "ca-pub-4557554518872474"
ADSENSE_ALLOWED_STATIC_PATHS = frozenset(
    {
        "/",
        "/about",
        "/usage",
        "/articles",
    }
)


def _is_adsense_allowed_path(path: str) -> bool:
    """AdSense はツール画面へ出さず、公開コンテンツだけで読み込む。"""
    normalized_path = path.rstrip("/") or "/"
    if normalized_path in ADSENSE_ALLOWED_STATIC_PATHS:
        return True

    try:
        from Articles.articles_registry import get_indexable_articles

        article_paths = {f"/{article['slug']}" for article in get_indexable_articles()}
    except Exception:
        article_paths = set()
    return normalized_path in article_paths


def _is_operation_page(path: str) -> bool:
    """操作画面かどうかを共通判定し、SEO メタタグを一貫させる。"""
    normalized_path = path.rstrip("/") or "/"
    if normalized_path in {
        "/fs-qr",
        "/upload",
        "/search_fs-qr",
        "/try_login",
        "/remove-succes",
        "/group",
        "/create_room",
        "/search_group",
        "/manage_rooms",
        "/logout_management",
        "/note",
        "/create_note_room",
        "/search_note",
        "/search_note_process",
        "/note_direct",
        "/task",
        "/create_task_room",
        "/search_task",
        "/search_task_process",
    }:
        return True

    return normalized_path.startswith(
        (
            "/fs-qr/",
            "/upload_complete/",
            "/download/",
            "/group/",
            "/delete_room/",
            "/note/",
            "/note_direct/",
            "/task/",
        )
    )


@pass_context
def url_for(context: Dict[str, Any], name: str, **params: Any) -> str:
    request: Request = context.get("request")  # type: ignore[assignment]
    if request is None:
        return ""
    external = bool(params.pop("_external", False))
    url = request.url_for(name, **params)
    if external:
        return str(url)
    return url.path


@pass_context
def get_flashed_messages(context: Dict[str, Any]) -> Iterable[str]:
    request: Request = context.get("request")  # type: ignore[assignment]
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
        query_token = _normalize_csrf_token(query_params.get(CSRF_FORM_FIELD))  # type: ignore[union-attr]
        if query_token:
            return query_token

    headers = getattr(websocket, "headers", None)
    if hasattr(headers, "get"):
        header_token = _normalize_csrf_token(headers.get(CSRF_HEADER_NAME))  # type: ignore[union-attr]
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
    request: Request = context.get("request")  # type: ignore[assignment]
    if request is None:
        return ""
    return get_or_create_csrf_token(request)


logger = logging.getLogger(__name__)


def render_template(request: Request, template_name: str, **context: Any):
    language = resolve_language(request)
    adsense_client_id = (
        GOOGLE_ADSENSE_CLIENT_ID if _is_adsense_allowed_path(request.url.path) else None
    )
    language_options = get_language_options(language)
    if JAPANESE_ONLY_MODE:
        # 言語データは保持したまま、審査中の UI からは日本語だけを提示する。
        language_options = tuple(
            option for option in language_options if option["code"] == DEFAULT_LANGUAGE
        )
    payload = {
        "request": TemplateRequestProxy(request),
        "current_language": language,
        "language_options": language_options,
        "frontend_messages": get_frontend_messages(language),
        "t": make_translator(language),
        "google_analytics_id": GOOGLE_ANALYTICS_ID,
        "google_adsense_client_id": adsense_client_id,
        "google_adsense_account_id": adsense_client_id,
        "force_noindex": _is_operation_page(request.url.path),
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


RENDER_CACHE_KEY_PREFIX = "render_cache:v4"
RENDER_CACHE_CSRF_PLACEHOLDER = "__FSQR_CSRF_TOKEN_PLACEHOLDER__"


def _render_cache_key(template_name: str, language: str, request: Request) -> str:
    # ?lang= の有無で canonical_url が変わるため、クエリの生値もキーに含める
    raw_lang = ""
    qp = getattr(request, "query_params", None)
    if qp is not None:
        raw_lang = (qp.get("lang") or "").strip().lower()
    url = getattr(request, "url", None)
    public_base = PUBLIC_SITE_URL or ""
    request_scheme = getattr(url, "scheme", "")
    request_host = getattr(url, "netloc", "")
    payload = (
        f"{template_name}|{language}|{raw_lang}|{int(bool(FRONTEND_DEBUG))}|"
        f"{public_base}|{request_scheme}|{request_host}"
    )
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
        cached_value = await redis_client.get(cache_key)
        cached_body = (
            cached_value.decode("utf-8")
            if isinstance(cached_value, bytes)
            else cached_value
        )
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


def _filter_retention_label(hours: Any) -> str:
    """保存期間の時間数を「1日」「1週間」「1か月」のような表示用ラベルに変換する。

    Note/Task の自動削除期間表示で使用。想定外の値は「n時間」にフォールバックする。
    """
    try:
        hours_int = int(hours)
    except (TypeError, ValueError):
        return f"{hours}時間"
    if hours_int == 24 * 30:
        return "1か月"
    if hours_int == 24 * 7:
        return "1週間"
    if hours_int == 24:
        return "1日"
    if hours_int > 0 and hours_int % 24 == 0:
        return f"{hours_int // 24}日"
    return f"{hours_int}時間"


templates.env.filters["datetime"] = _filter_datetime
# Provide a safe urlencode filter even if not present.
templates.env.filters.setdefault("urlencode", _filter_urlencode)
templates.env.filters["retention_label"] = _filter_retention_label

templates.env.globals.update(
    staticfile=staticfile,
    social_staticfile=social_staticfile,
    url_for=url_for,
    get_flashed_messages=get_flashed_messages,
    csrf_token=csrf_token,
    frontend_debug=FRONTEND_DEBUG,
    upload_max_files=UPLOAD_MAX_FILES,
    upload_max_total_size_mb=UPLOAD_MAX_TOTAL_SIZE_MB,
    upload_max_total_size_bytes=UPLOAD_MAX_TOTAL_SIZE_BYTES,
    note_max_content_length=NOTE_MAX_CONTENT_LENGTH,
    note_self_edit_timeout_ms=NOTE_SELF_EDIT_TIMEOUT_MS,
    task_max_items_per_room=TASK_MAX_ITEMS_PER_ROOM,
    task_max_title_length=TASK_MAX_TITLE_LENGTH,
    task_max_note_length=TASK_MAX_NOTE_LENGTH,
    task_max_tag_length=TASK_MAX_TAG_LENGTH,
    task_max_tags_per_room=TASK_MAX_TAGS_PER_ROOM,
    task_max_tags_per_item=TASK_MAX_TAGS_PER_ITEM,
    group_file_list_poll_interval_ms=GROUP_FILE_LIST_POLL_INTERVAL_MS,
    group_file_list_request_timeout_ms=GROUP_FILE_LIST_REQUEST_TIMEOUT_MS,
)
