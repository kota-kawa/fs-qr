from __future__ import annotations

from typing import Any, Mapping

from fastapi import Request
from starlette.responses import JSONResponse, Response

from i18n import current_language_ctx, get_frontend_messages, get_translator
from web import error_page, wants_json_response


def _normalize_data(data: Mapping[str, Any] | None) -> dict[str, Any]:
    if data is None:
        return {}
    return dict(data)


def api_ok_payload(data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"status": "ok", "data": _normalize_data(data), "error": None}


def api_error_payload(
    error: str, data: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    lang = current_language_ctx.get()

    # Server errors use the same Babel catalog as Jinja.  JSON JS messages are
    # retained only as a compatibility fallback for API callers that pass a
    # browser message key.
    translated_error = get_translator(lang)(error)
    if translated_error == error:
        translated_error = get_frontend_messages(lang).get(error, error)

    return {
        "status": "error",
        "data": _normalize_data(data),
        "error": str(translated_error),
    }


def api_ok_response(
    data: Mapping[str, Any] | None = None, *, status_code: int = 200
) -> JSONResponse:
    return JSONResponse(api_ok_payload(data), status_code=status_code)


def api_error_response(
    error: str,
    *,
    status_code: int = 400,
    data: Mapping[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(api_error_payload(error, data), status_code=status_code)


def error_page_or_json(
    request: Request,
    message: str,
    *,
    status_code: int,
    data: Mapping[str, Any] | None = None,
) -> Response:
    """fetch には JSON、ブラウザ遷移には error.html を返すエラー応答。

    JSON か HTML かの判定は :func:`web.wants_json_response` に一本化している。
    """
    if wants_json_response(request):
        return api_error_response(message, status_code=status_code, data=data)
    return error_page(request, message, status_code=status_code)
