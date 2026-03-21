"""CSRF protection for FastAPI/Starlette applications.

Generates per-session tokens and validates them on state-changing requests
(POST, PUT, PATCH, DELETE).
"""

import secrets

from fastapi import Request
from starlette.responses import JSONResponse

CSRF_SESSION_KEY = "_csrf_token"
CSRF_FIELD_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
TOKEN_LENGTH = 64

# Routes exempt from CSRF validation (e.g. API endpoints with their own auth).
EXEMPT_PATHS: set[str] = {
    "/api/note",  # Note API uses room_id/password auth per request
}

# HTTP methods that require CSRF validation.
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def generate_csrf_token(request: Request) -> str:
    """Return the existing CSRF token or create a new one in the session."""
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_hex(TOKEN_LENGTH)
        request.session[CSRF_SESSION_KEY] = token
    return token


def _is_exempt(path: str) -> bool:
    """Check if the request path is exempt from CSRF validation."""
    for exempt in EXEMPT_PATHS:
        if path.startswith(exempt):
            return True
    return False


async def _get_submitted_token(request: Request) -> str | None:
    """Extract the CSRF token from the request header or form body."""
    # 1. Check header first (used by JS fetch/AJAX calls).
    token = request.headers.get(CSRF_HEADER_NAME)
    if token:
        return token

    # 2. Check form body for regular form submissions.
    content_type = request.headers.get("content-type", "")
    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        try:
            form = await request.form()
            token = form.get(CSRF_FIELD_NAME)
            if token:
                return str(token)
        except Exception:
            pass

    return None


async def validate_csrf(request: Request) -> str | None:
    """Validate CSRF token. Returns an error message or None if valid."""
    if request.method not in UNSAFE_METHODS:
        return None

    if _is_exempt(request.url.path):
        return None

    session_token = request.session.get(CSRF_SESSION_KEY)
    if not session_token:
        return (
            "CSRFトークンがセッションに存在しません。ページを再読み込みしてください。"
        )

    submitted_token = await _get_submitted_token(request)
    if not submitted_token:
        return "CSRFトークンが送信されていません。ページを再読み込みしてください。"

    if not secrets.compare_digest(session_token, submitted_token):
        return "CSRFトークンが無効です。ページを再読み込みしてください。"

    return None


def csrf_error_response(request: Request, message: str):
    """Return an appropriate 403 response for CSRF failures."""
    content_type = request.headers.get("content-type", "")
    accept = request.headers.get("accept", "")
    is_ajax = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or "application/json" in accept
        or "application/json" in content_type
    )
    if is_ajax or "multipart/form-data" in content_type:
        return JSONResponse({"error": message}, status_code=403)
    # For regular form submissions, return a simple HTML error.
    from web import render_template

    response = render_template(request, "error.html", message=message)
    response.status_code = 403
    return response
