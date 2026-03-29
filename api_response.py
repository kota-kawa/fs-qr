from __future__ import annotations

from typing import Any, Mapping

from starlette.responses import JSONResponse


def _normalize_data(data: Mapping[str, Any] | None) -> dict[str, Any]:
    if data is None:
        return {}
    return dict(data)


def api_ok_payload(data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {"status": "ok", "data": _normalize_data(data), "error": None}


def api_error_payload(
    error: str, data: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return {"status": "error", "data": _normalize_data(data), "error": str(error)}


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
