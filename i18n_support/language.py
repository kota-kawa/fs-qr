from collections.abc import Callable

from fastapi import Request

from .constants import (
    COUNTRY_LANGUAGE_MAP,
    DEFAULT_LANGUAGE,
    LANGUAGE_COOKIE_NAME,
    SUPPORTED_LANGUAGES,
)


def normalize_language(language: str) -> str:  # noqa: C901
    if not language:
        return DEFAULT_LANGUAGE
    lowered = language.lower()
    if lowered in SUPPORTED_LANGUAGES:
        return lowered

    # Handle aliases and variants
    if lowered.startswith("ja") or lowered.startswith("jp"):
        return "ja"
    if lowered in {"zh-cn", "zh_cn", "zh-hans", "zh_hans", "cn"}:
        return "zh-CN"
    if lowered in {"zh-tw", "zh_tw", "zh-hant", "zh_hant", "tw", "hk", "mo"}:
        return "zh-TW"
    if lowered.startswith("ko") or lowered == "kr":
        return "ko"
    if lowered.startswith("fr"):
        return "fr"
    if lowered.startswith("es"):
        return "es"
    if lowered.startswith("de"):
        return "de"
    if lowered.startswith("pt"):
        return "pt"
    if lowered.startswith("it"):
        return "it"
    if lowered.startswith("ru"):
        return "ru"
    if lowered.startswith("nl"):
        return "nl"
    if lowered.startswith("hi"):
        return "hi"
    if lowered.startswith("bn"):
        return "bn"
    if lowered.startswith("vi"):
        return "vi"
    if lowered.startswith("th"):
        return "th"
    if lowered.startswith("id"):
        return "id"
    if lowered.startswith("tr"):
        return "tr"
    if lowered.startswith("uk"):
        return "uk"
    if lowered.startswith("pl"):
        return "pl"
    if lowered.startswith("sw"):
        return "sw"
    if lowered.startswith("ar"):
        return "ar"
    if lowered.startswith("en"):
        return "en"

    return DEFAULT_LANGUAGE


def language_from_country(country_code: str) -> str:
    if not country_code:
        return DEFAULT_LANGUAGE
    return COUNTRY_LANGUAGE_MAP.get(country_code.upper(), DEFAULT_LANGUAGE)


def resolve_language(
    request: Request,
    country_code_lookup: Callable[[str], str | None] | None = None,
) -> str:
    # 1. Query parameter (highest priority for switching)
    language = request.query_params.get("lang")
    if language and language in SUPPORTED_LANGUAGES:
        return language
    # Also support aliases in query params
    if language:
        normalized = normalize_language(language)
        if normalized in SUPPORTED_LANGUAGES and normalized != DEFAULT_LANGUAGE:
            return normalized
        if language.lower() in ("ja", "jp") and "ja" in SUPPORTED_LANGUAGES:
            return "ja"

    # 2. Cookie
    language = request.cookies.get(LANGUAGE_COOKIE_NAME)
    if language and language in SUPPORTED_LANGUAGES:
        return language

    # AdSense 再審査中は、IP 位置情報によるサーバー側の自動翻訳表示をしない。
    # Googlebot は主に米国から、Accept-Language なしでクロールするため、未選択時は
    # canonical の日本語ページを安定して返す。
    return DEFAULT_LANGUAGE


def is_language_query_only(request: Request) -> bool:
    params = request.query_params
    # Use multi_items() if available (for DummyQueryParams in tests)
    items = (
        params.multi_items() if hasattr(params, "multi_items") else list(params.items())
    )
    if len(items) != 1:
        return False
    lang = params.get("lang")
    if not lang:
        return False

    lowered = lang.lower()
    if lowered.startswith("ja") or lowered.startswith("jp"):
        return True
    normalized = normalize_language(lang)
    return normalized in SUPPORTED_LANGUAGES and normalized != DEFAULT_LANGUAGE
