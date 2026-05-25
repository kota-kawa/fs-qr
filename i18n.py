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

SUPPORTED_LANGUAGES = (
    "ja",
    "en",
    "zh-CN",
    "zh-TW",
    "ko",
    "fr",
    "es",
    "de",
    "pt",
    "it",
    "vi",
    "th",
    "id",
    "tr",
    "uk",
    "ru",
    "nl",
    "hi",
    "bn",
    "pl",
    "sw",
    "ar",
)
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
    {"code": "pt", "label": "Português", "flag": "🇵🇹"},
    {"code": "it", "label": "Italiano", "flag": "🇮🇹"},
    {"code": "ru", "label": "Русский", "flag": "🇷🇺"},
    {"code": "nl", "label": "Nederlands", "flag": "🇳🇱"},
    {"code": "hi", "label": "हिन्दी", "flag": "🇮🇳"},
    {"code": "bn", "label": "বাংলা", "flag": "🇧🇩"},
    {"code": "vi", "label": "Tiếng Việt", "flag": "🇻🇳"},
    {"code": "th", "label": "ไทย", "flag": "🇹🇭"},
    {"code": "id", "label": "Bahasa Indonesia", "flag": "🇮🇩"},
    {"code": "tr", "label": "Türkçe", "flag": "🇹🇷"},
    {"code": "uk", "label": "Українська", "flag": "🇺🇦"},
    {"code": "pl", "label": "Polski", "flag": "🇵🇱"},
    {"code": "sw", "label": "Kiswahili", "flag": "🇹🇿"},
    {"code": "ar", "label": "العربية", "flag": "🇸🇦"},
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
    "PT": "pt",
    "BR": "pt",
    "IT": "it",
    "RU": "ru",
    "BY": "ru",
    "KZ": "ru",
    "KG": "ru",
    "NL": "nl",
    "BE": "nl",
    "IN": "hi",
    "BD": "bn",
    "VN": "vi",
    "TH": "th",
    "ID": "id",
    "TR": "tr",
    "UA": "uk",
    "PL": "pl",
    "TZ": "sw",
    "KE": "sw",
    "UG": "sw",
    "SA": "ar",
    "AE": "ar",
    "EG": "ar",
    "JO": "ar",
    "KW": "ar",
    "QA": "ar",
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
    "pt": "pt",
    "it": "it",
    "ru": "ru",
    "nl": "nl",
    "hi": "hi",
    "bn": "bn",
    "vi": "vi",
    "th": "th",
    "id": "id",
    "tr": "tr",
    "uk": "uk",
    "pl": "pl",
    "sw": "sw",
    "ar": "ar",
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
    "pt": "pt",
    "it": "it",
    "ru": "ru",
    "nl": "nl",
    "hi": "hi",
    "bn": "bn",
    "vi": "vi",
    "th": "th",
    "id": "id",
    "tr": "tr",
    "uk": "uk",
    "pl": "pl",
    "sw": "sw",
    "ar": "ar",
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
    "pt": "pt_PT",
    "it": "it_IT",
    "ru": "ru_RU",
    "nl": "nl_NL",
    "hi": "hi_IN",
    "bn": "bn_BD",
    "vi": "vi_VN",
    "th": "th_TH",
    "id": "id_ID",
    "tr": "tr_TR",
    "uk": "uk_UA",
    "pl": "pl_PL",
    "sw": "sw_TZ",
    "ar": "ar_SA",
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
    "pt": "pt",
    "it": "it",
    "ru": "ru",
    "nl": "nl",
    "hi": "hi",
    "bn": "bn",
    "vi": "vi",
    "th": "th",
    "id": "id",
    "tr": "tr",
    "uk": "uk",
    "pl": "pl",
    "sw": "sw",
    "ar": "ar",
}
# 言語ごとの代表的な地域 (geo.region は ISO 3166-1 alpha-2)。
# 元のテンプレートは JP 固定だったが、各言語の主要な利用地域に対応させる。
GEO_REGION_MAP = {
    "ja": ("JP", "Japan"),
    "en": ("US", "United States"),
    "zh-CN": ("CN", "China"),
    "zh-TW": ("TW", "Taiwan"),
    "ko": ("KR", "South Korea"),
    "fr": ("FR", "France"),
    "es": ("ES", "Spain"),
    "de": ("DE", "Germany"),
    "pt": ("PT", "Portugal"),
    "it": ("IT", "Italy"),
    "ru": ("RU", "Russia"),
    "nl": ("NL", "Netherlands"),
    "hi": ("IN", "India"),
    "bn": ("BD", "Bangladesh"),
    "vi": ("VN", "Vietnam"),
    "th": ("TH", "Thailand"),
    "id": ("ID", "Indonesia"),
    "tr": ("TR", "Türkiye"),
    "uk": ("UA", "Ukraine"),
    "pl": ("PL", "Poland"),
    "sw": ("TZ", "Tanzania"),
    "ar": ("SA", "Saudi Arabia"),
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
    "pt": ("en",),
    "it": ("en",),
    "ru": ("en",),
    "nl": ("en",),
    "hi": ("en",),
    "bn": ("en",),
    "vi": ("en",),
    "th": ("en",),
    "id": ("en",),
    "tr": ("en",),
    "uk": ("en",),
    "pl": ("en",),
    "sw": ("en",),
    "ar": ("en",),
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
_GEO_REGION_RE = re.compile(
    r"<meta\s+name=[\"']geo\.region[\"']\s+content=[\"'][^\"']*[\"']", re.I
)
_GEO_PLACENAME_RE = re.compile(
    r"<meta\s+name=[\"']geo\.placename[\"']\s+content=[\"'][^\"']*[\"']", re.I
)


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


def get_country_code(ip: str) -> str | None:
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private:
            return None
    except ValueError:
        return None

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
    options: list[dict[str, str]] = []
    for option in LANGUAGE_OPTIONS:
        code = option["code"]
        translation_key = f"language.option.{code}"
        label = translate(translation_key)
        if label == translation_key:
            label = option["label"]
        options.append(
            {
                "code": code,
                "label": label,
                "flag": option["flag"],
            }
        )
    return tuple(options)


def translate_rendered_html(content: str, language: str) -> str:
    normalized_language = normalize_language(language)
    translations = load_translations()

    # 1. Update <html lang="..."> and handle dir="rtl" for Arabic
    html_lang = HTML_LANG_MAP.get(normalized_language, normalized_language)
    html_dir = "rtl" if normalized_language == "ar" else "ltr"

    def _replace_html_lang(match):
        attrs = match.group("attrs")
        # Remove existing dir attribute if any
        attrs = re.sub(r"\s*dir=[\"'][^\"']*[\"']", "", attrs, flags=re.I)
        return f'<html{attrs.rstrip()} lang="{html_lang}" dir="{html_dir}"'

    content = _HTML_LANG_RE.sub(_replace_html_lang, content)

    # 2. Update <meta http-equiv="content-language" content="..."> or <meta name="language" content="...">
    meta_lang = META_LANGUAGE_MAP.get(normalized_language, normalized_language)

    def _replace_meta_lang(match):
        original = match.group(0)
        if (
            'name="language"' in original.lower()
            or "name='language'" in original.lower()
        ):
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

    # 5. Update geo.region / geo.placename so the page advertises the locale's
    #    primary region instead of hard-coded JP/Japan from the template.
    region, placename = GEO_REGION_MAP.get(
        normalized_language, GEO_REGION_MAP[DEFAULT_LANGUAGE]
    )
    content = _GEO_REGION_RE.sub(f'<meta name="geo.region" content="{region}"', content)
    content = _GEO_PLACENAME_RE.sub(
        f'<meta name="geo.placename" content="{placename}"', content
    )

    # 6. Translate phrases
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
