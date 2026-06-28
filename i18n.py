from fastapi import Request

from i18n_support.catalog import (
    get_phrase_translation,
    get_translation_value,
    load_translations,
)
from i18n_support.constants import (
    COUNTRY_LANGUAGE_MAP,
    DEFAULT_LANGUAGE,
    GEO_REGION_MAP,
    HTML_LANG_MAP,
    LANGUAGE_COOKIE_MAX_AGE_SECONDS,
    LANGUAGE_COOKIE_NAME,
    LANGUAGE_FALLBACKS,
    LANGUAGE_OPTIONS,
    META_LANGUAGE_MAP,
    OG_LOCALE_MAP,
    SCHEMA_LANGUAGE_MAP,
    SUPPORTED_LANGUAGES,
    current_language_ctx,
)
from i18n_support.frontend import (
    get_frontend_messages,
    get_language_options,
    make_translator,
)
from i18n_support.geoip import (
    _geoip_reader_cache,
    _get_geoip_reader as _default_geoip_reader,
)
from i18n_support.geoip import get_country_code as _get_country_code
from i18n_support.html import (
    _HTML_LANG_RE,
    _LD_JSON_OPEN_RE,
    _META_DESCRIPTION_RE,
    _META_KEYWORDS_RE,
    _META_LANG_RE,
    _OG_LOCALE_RE,
    _PROTECTED_BLOCK_RE,
    _SCHEMA_LANG_RE,
    _GEO_PLACENAME_RE,
    _GEO_REGION_RE,
    _apply_phrase_replacements,
    _json_string_escape,
    _replace_phrases_in_html,
    _replace_phrases_in_protected_block,
    _uk_plural_articles,
    translate_rendered_html,
)
from i18n_support.language import (
    is_language_query_only,
    language_from_country,
    normalize_language,
)
from i18n_support.language import resolve_language as _resolve_language


def _get_geoip_reader():
    return _default_geoip_reader()


def get_country_code(ip: str) -> str | None:
    return _get_country_code(ip, reader_factory=_get_geoip_reader)


def resolve_language(request: Request) -> str:
    return _resolve_language(request, country_code_lookup=get_country_code)


__all__ = [
    "COUNTRY_LANGUAGE_MAP",
    "DEFAULT_LANGUAGE",
    "GEO_REGION_MAP",
    "HTML_LANG_MAP",
    "LANGUAGE_COOKIE_MAX_AGE_SECONDS",
    "LANGUAGE_COOKIE_NAME",
    "LANGUAGE_FALLBACKS",
    "LANGUAGE_OPTIONS",
    "META_LANGUAGE_MAP",
    "OG_LOCALE_MAP",
    "SCHEMA_LANGUAGE_MAP",
    "SUPPORTED_LANGUAGES",
    "_GEO_PLACENAME_RE",
    "_GEO_REGION_RE",
    "_HTML_LANG_RE",
    "_LD_JSON_OPEN_RE",
    "_META_DESCRIPTION_RE",
    "_META_KEYWORDS_RE",
    "_META_LANG_RE",
    "_OG_LOCALE_RE",
    "_PROTECTED_BLOCK_RE",
    "_SCHEMA_LANG_RE",
    "_apply_phrase_replacements",
    "_geoip_reader_cache",
    "_get_geoip_reader",
    "_json_string_escape",
    "_replace_phrases_in_html",
    "_replace_phrases_in_protected_block",
    "_uk_plural_articles",
    "current_language_ctx",
    "get_country_code",
    "get_frontend_messages",
    "get_language_options",
    "get_phrase_translation",
    "get_translation_value",
    "is_language_query_only",
    "language_from_country",
    "load_translations",
    "make_translator",
    "normalize_language",
    "resolve_language",
    "translate_rendered_html",
]
