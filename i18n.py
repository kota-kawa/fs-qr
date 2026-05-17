import ipaddress
import json
import logging
import os
import re
from functools import lru_cache
from html import escape
from typing import Any

from fastapi import Request

from settings import BASE_DIR, GEOIP_DB_PATH

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("ja", "en", "zh-CN", "zh-TW", "ko")
DEFAULT_LANGUAGE = "ja"
LANGUAGE_COOKIE_NAME = "fsqr_language"
LANGUAGE_COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60

LANGUAGE_OPTIONS = (
    {"code": "ja", "label": "日本語", "flag": "🇯🇵"},
    {"code": "en", "label": "English", "flag": "🇺🇸"},
    {"code": "zh-CN", "label": "简体中文", "flag": "🇨🇳"},
    {"code": "zh-TW", "label": "繁體中文", "flag": "🇹🇼"},
    {"code": "ko", "label": "한국어", "flag": "🇰🇷"},
)

COUNTRY_LANGUAGE_MAP = {
    "JP": "ja",
    "CN": "zh-CN",
    "SG": "zh-CN",
    "HK": "zh-TW",
    "MO": "zh-TW",
    "TW": "zh-TW",
    "KR": "ko",
}

HTML_LANG_MAP = {
    "ja": "ja",
    "en": "en",
    "zh-CN": "zh-CN",
    "zh-TW": "zh-TW",
    "ko": "ko",
}
META_LANGUAGE_MAP = {
    "ja": "ja",
    "en": "en",
    "zh-CN": "zh-CN",
    "zh-TW": "zh-TW",
    "ko": "ko",
}
OG_LOCALE_MAP = {
    "ja": "ja_JP",
    "en": "en_US",
    "zh-CN": "zh_CN",
    "zh-TW": "zh_TW",
    "ko": "ko_KR",
}
SCHEMA_LANGUAGE_MAP = {
    "ja": "ja-JP",
    "en": "en",
    "zh-CN": "zh-CN",
    "zh-TW": "zh-TW",
    "ko": "ko",
}
LANGUAGE_FALLBACKS = {
    "ja": (),
    "en": (),
    "zh-CN": ("en",),
    "zh-TW": ("zh-CN", "en"),
    "ko": ("en",),
}

_geoip_reader_cache: dict[str, Any] = {"path": None, "mtime": None, "reader": None}

_HTML_LANG_RE = re.compile(r"<html(?P<attrs>[^>]*)\blang=[\"'][^\"']*[\"']", re.I)
_META_LANGUAGE_RE = re.compile(
    r'(<meta\s+name=["\']language["\']\s+content=["\'])[^"\']*(["\'])', re.I
)
_OG_LOCALE_RE = re.compile(
    r'(<meta\s+property=["\']og:locale["\']\s+content=["\'])[^"\']*(["\'])',
    re.I,
)
_SCHEMA_LANGUAGE_RE = re.compile(r'("inLanguage"\s*:\s*")[^"]*(")')


def normalize_language(value: Any) -> str:
    if not isinstance(value, str):
        return DEFAULT_LANGUAGE
    value = value.strip()
    if value in SUPPORTED_LANGUAGES:
        return value
    lowered = value.lower()
    if lowered in {"zh", "zh-cn", "zh_hans", "zh-hans", "cn"}:
        return "zh-CN"
    if lowered in {"zh-tw", "zh_tw", "zh-hant", "zh_hant", "tw", "hk", "mo"}:
        return "zh-TW"
    if lowered.startswith("ko") or lowered == "kr":
        return "ko"
    if lowered.startswith("en"):
        return "en"
    if lowered.startswith("ja") or lowered.startswith("jp"):
        return "ja"
    return DEFAULT_LANGUAGE


def is_language_query_only(request: Request) -> bool:
    query_params = getattr(request, "query_params", None)
    if query_params is None or not hasattr(query_params, "multi_items"):
        return False
    params = list(query_params.multi_items())
    if len(params) != 1 or params[0][0] != "lang":
        return False

    raw_language = params[0][1]
    if not isinstance(raw_language, str) or not raw_language.strip():
        return False

    normalized = normalize_language(raw_language)
    raw_normalized = raw_language.strip().lower()
    valid_default_alias = raw_normalized in {"ja", "jp", "ja-jp"}
    return normalized != DEFAULT_LANGUAGE or valid_default_alias


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip
    if getattr(request, "client", None) and request.client:
        return request.client.host
    return ""


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _get_geoip_reader():
    db_path = GEOIP_DB_PATH
    if not db_path:
        return None
    if not os.path.isabs(db_path):
        db_path = os.path.join(BASE_DIR, db_path)
    if not os.path.exists(db_path):
        logger.info("GeoIP database not found at %s; falling back to Japanese", db_path)
        return None
    try:
        import maxminddb
    except ImportError:
        logger.warning("maxminddb is not installed; GeoIP language detection disabled")
        return None
    mtime = os.path.getmtime(db_path)
    cached_reader = _geoip_reader_cache.get("reader")
    if (
        cached_reader is not None
        and _geoip_reader_cache.get("path") == db_path
        and _geoip_reader_cache.get("mtime") == mtime
    ):
        return cached_reader

    if cached_reader is not None and hasattr(cached_reader, "close"):
        try:
            cached_reader.close()
        except Exception:
            pass

    try:
        reader = maxminddb.open_database(db_path)
        _geoip_reader_cache.update({"path": db_path, "mtime": mtime, "reader": reader})
        return reader
    except Exception as exc:  # pragma: no cover - depends on local DB integrity
        logger.warning("Failed to open GeoIP database %s: %s", db_path, exc)
        return None


def language_from_country(country_code: Any) -> str:
    if not isinstance(country_code, str):
        return DEFAULT_LANGUAGE
    normalized = country_code.strip().upper()
    if not normalized:
        return DEFAULT_LANGUAGE
    return COUNTRY_LANGUAGE_MAP.get(normalized, "en")


def language_from_ip(ip_address: str) -> str:
    if not ip_address or not _is_public_ip(ip_address):
        return DEFAULT_LANGUAGE
    reader = _get_geoip_reader()
    if reader is None:
        return DEFAULT_LANGUAGE
    try:
        record = reader.get(ip_address)
    except Exception:
        return DEFAULT_LANGUAGE
    country = (record or {}).get("country", {})
    country_code = country.get("iso_code") or (record or {}).get("country_code")
    return language_from_country(country_code)


def resolve_language(request: Request) -> str:
    # ?lang= クエリパラメータが最優先（hreflang用URLからのアクセスとクローラー対応）
    query_params = getattr(request, "query_params", None)
    raw_query_language = query_params.get("lang") if query_params is not None else None
    if isinstance(raw_query_language, str) and raw_query_language.strip():
        normalized = normalize_language(raw_query_language)
        raw_normalized = raw_query_language.strip().lower()
        valid_default_alias = raw_normalized in {"ja", "jp", "ja-jp"}
        if normalized != DEFAULT_LANGUAGE or valid_default_alias:
            return normalized
    raw_cookie_language = request.cookies.get(LANGUAGE_COOKIE_NAME)
    cookie_language = normalize_language(raw_cookie_language)
    if isinstance(raw_cookie_language, str) and raw_cookie_language.strip():
        raw_normalized = raw_cookie_language.strip().lower()
        valid_default_alias = raw_normalized in {"ja", "jp", "ja-jp"}
        if cookie_language != DEFAULT_LANGUAGE or valid_default_alias:
            return cookie_language
    return language_from_ip(_get_client_ip(request))


@lru_cache(maxsize=1)
def _load_translations() -> dict[str, dict[str, Any]]:
    translations: dict[str, dict[str, Any]] = {}
    for language in SUPPORTED_LANGUAGES:
        path = os.path.join(BASE_DIR, "locales", f"{language}.json")
        try:
            with open(path, encoding="utf-8") as fp:
                translations[language] = json.load(fp)
        except FileNotFoundError:
            translations[language] = {}
    return translations


def get_translation_value(language: str, section: str, key: str) -> str:
    language = normalize_language(language)
    translations = _load_translations()
    for code in (language, *LANGUAGE_FALLBACKS.get(language, ())):
        value = translations.get(code, {}).get(section, {}).get(key)
        if isinstance(value, str):
            return value
    return key


def get_frontend_messages(language: str) -> dict[str, str]:
    language = normalize_language(language)
    translations = _load_translations()
    messages: dict[str, Any] = {}
    for fallback_language in LANGUAGE_FALLBACKS.get(language, ()):
        messages.update(translations.get(fallback_language, {}).get("js", {}))
    messages.update(translations.get(language, {}).get("js", {}))
    return {key: value for key, value in messages.items() if isinstance(value, str)}


def make_translator(language: str):
    normalized_language = normalize_language(language)

    def translate(key: str, **params: Any) -> str:
        value = get_translation_value(normalized_language, "ui", key)
        if params:
            try:
                return value.format(**params)
            except Exception:
                return value
        return value

    return translate


def get_language_options(language: str) -> tuple[dict[str, str], ...]:
    translate = make_translator(language)
    labels = {
        "ja": translate("language.option.ja"),
        "en": translate("language.option.en"),
        "zh-CN": translate("language.option.zh-CN"),
        "zh-TW": translate("language.option.zh-TW"),
        "ko": translate("language.option.ko"),
    }
    options: list[dict[str, str]] = []
    for option in LANGUAGE_OPTIONS:
        code = option["code"]
        options.append(
            {
                "code": code,
                "label": labels.get(code, option["label"]),
                "flag": option["flag"],
            }
        )
    return tuple(options)


def _replace_language_metadata(content: str, language: str) -> str:
    html_lang = HTML_LANG_MAP.get(language, DEFAULT_LANGUAGE)
    meta_language = META_LANGUAGE_MAP.get(language, DEFAULT_LANGUAGE)
    og_locale = OG_LOCALE_MAP.get(language, OG_LOCALE_MAP[DEFAULT_LANGUAGE])
    schema_language = SCHEMA_LANGUAGE_MAP.get(
        language, SCHEMA_LANGUAGE_MAP[DEFAULT_LANGUAGE]
    )

    def replace_html_lang(match: re.Match[str]) -> str:
        attrs = match.group("attrs").rstrip()
        return f'<html{attrs} lang="{html_lang}"'

    content = _HTML_LANG_RE.sub(replace_html_lang, content, count=1)
    content = _META_LANGUAGE_RE.sub(
        lambda match: f"{match.group(1)}{meta_language}{match.group(2)}", content
    )
    content = _OG_LOCALE_RE.sub(
        lambda match: f"{match.group(1)}{og_locale}{match.group(2)}", content
    )
    content = _SCHEMA_LANGUAGE_RE.sub(
        lambda match: f"{match.group(1)}{schema_language}{match.group(2)}", content
    )
    return content


def _ensure_geoip_attribution(content: str) -> str:
    if "https://db-ip.com" in content:
        return content
    attribution = (
        '<div class="geoip-attribution" '
        'style="font-size:0.75rem;text-align:center;padding:0.5rem;color:inherit;">'
        '<a href="https://db-ip.com" target="_blank" rel="noopener noreferrer">'
        "IP Geolocation by DB-IP"
        "</a></div>"
    )
    if "</body>" in content:
        return content.replace("</body>", f"{attribution}</body>", 1)
    return f"{content}{attribution}"


def translate_rendered_html(content: str, language: str) -> str:
    language = normalize_language(language)
    content = _replace_language_metadata(content, language)
    if language == DEFAULT_LANGUAGE:
        return content

    translations = _load_translations()
    phrases: dict[str, Any] = {}
    for fallback_language in LANGUAGE_FALLBACKS.get(language, ()):
        fallback_phrases = translations.get(fallback_language, {}).get("phrases", {})
        if isinstance(fallback_phrases, dict):
            phrases.update(fallback_phrases)
    language_phrases = translations.get(language, {}).get("phrases", {})
    if isinstance(language_phrases, dict):
        phrases.update(language_phrases)
    if not phrases:
        return content

    for source in sorted(phrases, key=len, reverse=True):
        translated = phrases.get(source)
        if not isinstance(translated, str):
            continue
        content = content.replace(source, translated)
        content = content.replace(escape(source), escape(translated))
    return content
