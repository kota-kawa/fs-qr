from __future__ import annotations

from typing import Any, Mapping

from starlette.responses import JSONResponse


from i18n import current_language_ctx, get_translation_value, load_translations

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
    
    # 1. Try to translate in "ui" section (if error matches a ui key)
    translated_error = get_translation_value(lang, "ui", error)
    
    # 2. Try to translate in "phrases" section (since error message might be a phrase)
    if translated_error == error:
        translations = load_translations()
        translated_error = translations.get(lang, {}).get("phrases", {}).get(error, error)
        
    # 3. Try to translate in "js" section (just in case)
    if translated_error == error:
        translated_error = translations.get(lang, {}).get("js", {}).get(error, error)
        
    return {"status": "error", "data": _normalize_data(data), "error": str(translated_error)}


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
