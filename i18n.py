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

SUPPORTED_LANGUAGES = ("ja", "en", "zh-CN", "zh-TW", "ko", "fr", "es", "de")
DEFAULT_LANGUAGE = "ja"
LANGUAGE_COOKIE_NAME = "fsqr_language"
LANGUAGE_COOKIE_MAX_AGE_SECONDS = 365 * 24 * 60 * 60

LANGUAGE_OPTIONS = (
    {"code": "ja", "label": "日本語", "flag": "🇯🇵"},
    {"code": "en", "label": "English", "flag": "🇺🇸"},
    {"code": "zh-CN", "label": "简体中文", "flag": "🇨🇳"},
    {"code": "zh-TW", "label": "繁體中文", "flag": "🇹🇼"},
    {"code": "ko", "label": "한국어", "flag": "🇰🇷"},
    {"code": "fr", "label": "Français", "flag": "🇫🇷"},
    {"code": "es", "label": "Español", "flag": "🇪🇸"},
    {"code": "de", "label": "Deutsch", "flag": "🇩🇪"},
)

COUNTRY_LANGUAGE_MAP = {
    "JP": "ja",
    "CN": "zh-CN",
    "SG": "zh-CN",
    "HK": "zh-TW",
    "MO": "zh-TW",
    "TW": "zh-TW",
    "KR": "ko",
    "FR": "fr",
    "ES": "es",
    "MX": "es",
    "AR": "es",
    "CL": "es",
    "CO": "es",
    "PE": "es",
    "US": "en",
    "GB": "en",
    "AU": "en",
    "CA": "en",
    "NZ": "en",
    "DE": "de",
    "AT": "de",
    "CH": "de",
}

HTML_LANG_MAP = {
    "ja": "ja",
    "en": "en",
    "zh-CN": "zh-CN",
    "zh-TW": "zh-TW",
    "ko": "ko",
    "fr": "fr",
    "es": "es",
    "de": "de",
}
META_LANGUAGE_MAP = {
    "ja": "ja",
    "en": "en",
    "zh-CN": "zh-CN",
    "zh-TW": "zh-TW",
    "ko": "ko",
    "fr": "fr",
    "es": "es",
    "de": "de",
}
OG_LOCALE_MAP = {
    "ja": "ja_JP",
    "en": "en_US",
    "zh-CN": "zh_CN",
    "zh-TW": "zh_TW",
    "ko": "ko_KR",
    "fr": "fr_FR",
    "es": "es_ES",
    "de": "de_DE",
}
SCHEMA_LANGUAGE_MAP = {
    "ja": "ja-JP",
    "en": "en",
    "zh-CN": "zh-CN",
    "zh-TW": "zh-TW",
    "ko": "ko",
    "fr": "fr",
    "es": "es",
    "de": "de",
}
LANGUAGE_FALLBACKS = {
    "ja": (),
    "en": (),
    "zh-CN": ("en",),
    "zh-TW": ("zh-CN", "en"),
    "ko": ("en",),
    "fr": ("en",),
    "es": ("en",),
    "de": ("en",),
}

_geoip_reader_cache: dict[str, Any] = {"path": None, "mtime": None, "reader": None}

_HTML_LANG_RE = re.compile(r"<html(?P<attrs>[^>]*)\blang=[\"'][^\"']*[\"']", re.I)
_META_LANG_RE = re.compile(
    r"<meta\s+(?:http-equiv=[\"']content-language[\"']|name=[\"']language[\"'])\s+content=[\"'][^\"']*[\"']",
    re.I,
)
_OG_LOCALE_RE = re.compile(
    r"<meta\s+property=[\"']og:locale[\"']\s+content=[\"'][^\"']*[\"']", re.I
)
_SCHEMA_LANG_RE = re.compile(r"\"inLanguage\":\s*\"[^\"]*\"", re.I)


@lru_cache(maxsize=1)
def load_translations():
    translations = {}
    locales_dir = os.path.join(BASE_DIR, "locales")
    for lang in SUPPORTED_LANGUAGES:
        file_path = os.path.join(locales_dir, f"{lang}.json")
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    translations[lang] = json.load(f)
            except Exception as e:
                logger.error(f"Error loading translation for {lang}: {e}")
                translations[lang] = {}
        else:
            translations[lang] = {}
    return translations


def get_translation_value(language: str, section: str, key: str) -> str:
    translations = load_translations()
    normalized_language = normalize_language(language)

    # 1. Try specified language
    value = translations.get(normalized_language, {}).get(section, {}).get(key)
    if value:
        return value

    # 2. Try fallbacks
    fallbacks = LANGUAGE_FALLBACKS.get(normalized_language, ())
    for fallback in fallbacks:
        value = translations.get(fallback, {}).get(section, {}).get(key)
        if value:
            return value

    # 3. Try English if not already tried
    if normalized_language != "en" and "en" not in fallbacks:
        value = translations.get("en", {}).get(section, {}).get(key)
        if value:
            return value

    # 4. Try Japanese if not already tried
    if normalized_language != "ja" and "ja" not in fallbacks:
        value = translations.get("ja", {}).get(section, {}).get(key)
        if value:
            return value

    return key


def normalize_language(language: str) -> str:
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
    if lowered.startswith("en"):
        return "en"

    return DEFAULT_LANGUAGE


def language_from_country(country_code: str) -> str:
    if not country_code:
        return DEFAULT_LANGUAGE
    return COUNTRY_LANGUAGE_MAP.get(country_code.upper(), DEFAULT_LANGUAGE)


def resolve_language(request: Request) -> str:
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

    # 3. GeoIP
    ip = request.client.host if request.client else None
    if ip:
        country_code = get_country_code(ip)
        if country_code:
            language = language_from_country(country_code)
            if language in SUPPORTED_LANGUAGES:
                return language

    return DEFAULT_LANGUAGE


def is_language_query_only(request: Request) -> bool:
    params = request.query_params
    # Use multi_items() if available (for DummyQueryParams in tests)
    items = params.multi_items() if hasattr(params, "multi_items") else list(params.items())
    if len(items) != 1:
        return False
    lang = params.get("lang")
    if not lang:
        return False

    lowered = lang.lower()
    if lowered in SUPPORTED_LANGUAGES:
        return True

    # Handle aliases
    if lowered.startswith("ja") or lowered.startswith("jp"):
        return True
    if lowered in {"zh-cn", "zh_cn", "zh-hans", "zh_hans", "cn"}:
        return True
    if lowered in {"zh-tw", "zh_tw", "zh-hant", "zh_hant", "tw", "hk", "mo"}:
        return True
    if lowered.startswith("ko") or lowered == "kr":
        return True
    if lowered.startswith("fr"):
        return True
    if lowered.startswith("es"):
        return True
    if lowered.startswith("en"):
        return True

    return False


def get_country_code(ip: str) -> str | None:
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private:
            return None
    except ValueError:
        return None

    import maxminddb

    reader = _get_geoip_reader()
    if not reader:
        return None

    try:
        # maxminddb returns a dict
        record = reader.get(ip)
        if not record:
            return None
        # Support both standard GeoIP2/GeoLite2 (record['country']['iso_code'])
        # and flat schemas (record['country_code']) used in some DBs/tests
        if "country" in record and isinstance(record["country"], dict):
            return record["country"].get("iso_code")
        return record.get("country_code")
    except Exception:
        return None


def _get_geoip_reader():
    if not os.path.exists(GEOIP_DB_PATH):
        return None

    current_mtime = os.path.getmtime(GEOIP_DB_PATH)
    if (
        _geoip_reader_cache["path"] == GEOIP_DB_PATH
        and _geoip_reader_cache["mtime"] == current_mtime
    ):
        return _geoip_reader_cache["reader"]

    import maxminddb

    try:
        reader = maxminddb.open_database(GEOIP_DB_PATH)
        _geoip_reader_cache["path"] = GEOIP_DB_PATH
        _geoip_reader_cache["mtime"] = current_mtime
        _geoip_reader_cache["reader"] = reader
        return reader
    except Exception:
        return None


def get_frontend_messages(language: str) -> dict[str, str]:
    translations = load_translations()
    normalized_language = normalize_language(language)
    messages = {}

    # 1. English as base if not current language
    if normalized_language != "en":
        messages.update(translations.get("en", {}).get("js", {}))

    # 2. Current language overrides
    messages.update(translations.get(normalized_language, {}).get("js", {}))

    return messages


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
        "fr": translate("language.option.fr"),
        "es": translate("language.option.es"),
        "de": translate("language.option.de"),
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


def translate_rendered_html(content: str, language: str) -> str:
    normalized_language = normalize_language(language)
    translations = load_translations()

    # 1. Update <html lang="...">
    html_lang = HTML_LANG_MAP.get(normalized_language, normalized_language)

    def _replace_html_lang(match):
        attrs = match.group("attrs")
        return f'<html{attrs}lang="{html_lang}"'

    content = _HTML_LANG_RE.sub(_replace_html_lang, content)

    # 2. Update <meta http-equiv="content-language" content="..."> or <meta name="language" content="...">
    meta_lang = META_LANGUAGE_MAP.get(normalized_language, normalized_language)

    def _replace_meta_lang(match):
        original = match.group(0)
        if 'name="language"' in original.lower() or "name='language'" in original.lower():
            return f'<meta name="language" content="{meta_lang}"'
        return f'<meta http-equiv="content-language" content="{meta_lang}"'

    content = _META_LANG_RE.sub(_replace_meta_lang, content)

    # 3. Update <meta property="og:locale" content="...">
    og_locale = OG_LOCALE_MAP.get(normalized_language, "en_US")
    content = _OG_LOCALE_RE.sub(
        f'<meta property="og:locale" content="{og_locale}"', content
    )

    # 4. Update "inLanguage": "..." (Schema.org)
    schema_lang = SCHEMA_LANGUAGE_MAP.get(normalized_language, normalized_language)
    content = _SCHEMA_LANG_RE.sub(f'"inLanguage": "{schema_lang}"', content)

    # 5. Translate phrases
    phrases = {}
    fallbacks = LANGUAGE_FALLBACKS.get(normalized_language, ())
    for fallback_language in reversed(fallbacks):
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
