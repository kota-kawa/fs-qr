import logging
import os
import time
from html import escape
from typing import Any, Dict, Iterable
from urllib.parse import quote_plus

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.responses import HTMLResponse

from session_utils import session_get, session_pop, session_set
from settings import BASE_DIR

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

logger = logging.getLogger(__name__)


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
    accessible, messages = session_pop(request, "_flashes", [])
    if not accessible:
        return []
    if not isinstance(messages, list):
        return []
    return messages


def flash_message(request: Request, message: str) -> None:
    accessible, messages = session_get(request, "_flashes")
    if not accessible:
        logger.warning("Failed to flash message (session may be unavailable)")
        return
    if not isinstance(messages, list):
        messages = []
    messages.append(message)
    if not session_set(request, "_flashes", messages):
        logger.warning("Failed to flash message (session may be unavailable)")


def render_template(request: Request, template_name: str, **context: Any):
    payload = {"request": TemplateRequestProxy(request)}
    payload.update(context)
    requested_status = payload.pop("_status_code", None)
    try:
        try:
            response = templates.TemplateResponse(request, template_name, payload)
        except TypeError:
            response = templates.TemplateResponse(template_name, payload)
        if requested_status is not None:
            response.status_code = int(requested_status)
        return response
    except Exception as exc:
        logger.exception("Error rendering template %s: %s", template_name, exc)
        fallback_message = str(
            context.get("message")
            or "一時的なエラーが発生しました。時間をおいて再度お試しください。"
        )
        fallback_status = (
            int(requested_status)
            if requested_status and int(requested_status) >= 400
            else 500
        )
        title = "ページが見つかりません" if template_name == "404.html" else "エラー"
        body = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | FS!QR</title>
  <style>
    body {{
      margin: 0;
      font-family: sans-serif;
      background: #f5f5f5;
      color: #1f2937;
    }}
    main {{
      max-width: 640px;
      margin: 8vh auto;
      padding: 24px;
    }}
    section {{
      background: #fff;
      border: 1px solid #e5e7eb;
      border-radius: 16px;
      padding: 32px 24px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
      text-align: center;
    }}
    h1 {{
      margin: 0 0 16px;
      font-size: 1.5rem;
    }}
    p {{
      margin: 0 0 24px;
      line-height: 1.7;
    }}
    a {{
      display: inline-block;
      padding: 12px 20px;
      border-radius: 999px;
      background: #2563eb;
      color: #fff;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <main>
    <section>
      <h1>{escape(title)}</h1>
      <p>{escape(fallback_message)}</p>
      <a href="/">ホームへ戻る</a>
    </section>
  </main>
</body>
</html>
"""
        return HTMLResponse(body, status_code=fallback_status)


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


@pass_context
def csrf_token(context: Dict[str, Any]) -> str:
    from csrf import generate_csrf_token

    request: Request = context.get("request")
    if request is None:
        return ""
    try:
        return generate_csrf_token(request)
    except Exception:
        logger.warning("Failed to generate CSRF token (session may be unavailable)")
        return ""


templates.env.globals.update(
    staticfile=staticfile,
    url_for=url_for,
    get_flashed_messages=get_flashed_messages,
    csrf_token=csrf_token,
)
