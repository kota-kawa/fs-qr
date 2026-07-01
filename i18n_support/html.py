import html
import json
import re
from typing import Any

from .catalog import get_phrase_translation, get_translation_value, load_translations
from .constants import (
    DEFAULT_LANGUAGE,
    GEO_REGION_MAP,
    HTML_LANG_MAP,
    LANGUAGE_FALLBACKS,
    OG_LOCALE_MAP,
    SCHEMA_LANGUAGE_MAP,
)
from .language import normalize_language

_HTML_LANG_RE = re.compile(r"<html(?P<attrs>[^>]*)>", re.I)
_META_LANG_RE = re.compile(
    r"<meta\s+(?:http-equiv=['\"]content-language['\"]|name=['\"]language['\"])\s+content=['\"][^'\"]*['\"][^>]*>",
    re.I,
)

# New regex for meta description tag
_META_DESCRIPTION_RE = re.compile(
    r"<meta\s+name=['\"]description['\"]\s+content=['\"]([^'\"]*)['\"][^>]*>",
    re.I,
)
_META_KEYWORDS_RE = re.compile(
    r"<meta\s+name=['\"]keywords['\"]\s+content=['\"]([^'\"]*)['\"][^>]*>",
    re.I,
)
_ROBOTS_META_RE = re.compile(
    r"<meta\s+name=[\"']robots[\"']\s+content=[\"'](?P<content>[^\"']*)[\"'][^>]*>",
    re.I,
)
_GOOGLEBOT_META_RE = re.compile(
    r"<meta\s+name=[\"']googlebot[\"']\s+content=[\"'](?P<content>[^\"']*)[\"'][^>]*>",
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
# <script>/<style> blocks are protected from plain phrase replacement: blindly
# substituting a Japanese source string that happens to live inside JavaScript or
# CSS can inject quote characters from the translation (e.g. French "Copier l'URL")
# and break the surrounding string literal, which kills the whole block. When a
# block stops executing, buttons stop responding and QR codes never render.
_PROTECTED_BLOCK_RE = re.compile(
    r"<(?P<tag>script|style)\b[^>]*>.*?</(?P=tag)\s*>", re.I | re.S
)
_LD_JSON_OPEN_RE = re.compile(
    r"<script\b[^>]*\btype=[\"']application/ld\+json[\"']", re.I
)


def translate_rendered_html(content: str, language: str) -> str:
    normalized_language = normalize_language(language)
    translations = load_translations()

    # 1. Update <html lang="..."> and handle dir="rtl" for Arabic
    html_lang = HTML_LANG_MAP.get(normalized_language, normalized_language)
    html_dir = "rtl" if normalized_language == "ar" else "ltr"

    def _replace_html_lang(match):
        attrs = match.group("attrs")
        attrs = re.sub(r"\s*lang=['\"]?[^'\"\s>]*['\"]?", "", attrs, flags=re.I)
        attrs = re.sub(r"\s*dir=['\"]?[^'\"]*['\"]?", "", attrs, flags=re.I)
        return f'<html{attrs.rstrip()} lang="{html_lang}" dir="{html_dir}">'

    content = _HTML_LANG_RE.sub(_replace_html_lang, content)

    # 2b. Translate page-specific <meta name="description"> when available.
    # If a page-specific translation is missing, keep the previous common
    # description fallback for non-Japanese pages instead of leaking Japanese.
    def _replace_meta_desc(match):
        original_desc = match.group(1)
        translated_desc = original_desc
        if normalized_language != DEFAULT_LANGUAGE:
            translated_desc = get_phrase_translation(
                normalized_language, original_desc
            ) or get_translation_value(normalized_language, "ui", "meta.description")
        escaped_desc = html.escape(translated_desc, quote=True)
        return f'<meta name="description" content="{escaped_desc}">'

    content = _META_DESCRIPTION_RE.sub(_replace_meta_desc, content)

    # 2b-2. Localize <meta name="keywords"> per locale. Templates ship the
    # Japanese keyword set; on translated pages we swap in the locale's own
    # keywords when provided (locales/<lang>/ui.json -> "meta.keywords"), and
    # otherwise drop the tag so foreign-language pages never leak Japanese
    # keyword text. The keywords meta is ignored by Google/Bing, so removal is
    # safe; it still benefits engines that read it (e.g. Baidu) where localized.
    def _replace_meta_keywords(match):
        if normalized_language == DEFAULT_LANGUAGE:
            return match.group(0)
        localized = (
            translations.get(normalized_language, {}).get("ui", {}).get("meta.keywords")
        )
        if localized:
            escaped_keywords = html.escape(localized, quote=True)
            return f'<meta name="keywords" content="{escaped_keywords}">'
        return ""

    content = _META_KEYWORDS_RE.sub(_replace_meta_keywords, content)

    if normalized_language != DEFAULT_LANGUAGE:
        content = _ROBOTS_META_RE.sub(_replace_non_default_robots, content)
        content = _GOOGLEBOT_META_RE.sub(_replace_non_default_googlebot, content)

    # 2c. Update <meta name="language" content=...> with language code
    def _replace_meta_lang(match):
        return f'<meta name="language" content="{html_lang}">'

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
    language_phrases = translations.get(normalized_language, {}).get("phrases", {})
    if isinstance(language_phrases, dict):
        phrases.update(language_phrases)
    if not phrases:
        content = content
    else:
        content = _apply_phrase_replacements(content, phrases)

    if normalized_language == "uk":
        content = re.sub(
            r'(\d+)(</span>\s*<span class="articles-count-unit">)?\s*статей',
            _uk_plural_articles,
            content,
        )

    return content


def _non_default_robot_directive(existing_content: str) -> str:
    existing = existing_content.lower()
    return "noindex, nofollow" if "nofollow" in existing else "noindex, follow"


def _replace_non_default_robots(match) -> str:
    directive = _non_default_robot_directive(match.group("content"))
    return f'<meta name="robots" content="{directive}">'


def _replace_non_default_googlebot(match) -> str:
    directive = _non_default_robot_directive(match.group("content"))
    return f'<meta name="googlebot" content="{directive}">'


def _uk_plural_articles(match) -> str:
    num = int(match.group(1))
    sep = match.group(2) or ""
    mod10 = num % 10
    mod100 = num % 100
    if mod10 == 1 and mod100 != 11:
        word = "стаття"
    elif mod10 in (2, 3, 4) and mod100 not in (12, 13, 14):
        word = "статті"
    else:
        word = "статей"
    return f"{num}{sep} {word}"


def _json_string_escape(text: str) -> str:
    """Escape a value for safe embedding inside a JSON string literal."""
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _apply_phrase_replacements(content: str, phrases: dict[str, Any]) -> str:
    sources = [
        source
        for source in sorted(phrases, key=len, reverse=True)
        if isinstance(phrases.get(source), str)
    ]
    if not sources:
        return content

    result: list[str] = []
    last = 0
    for block in _PROTECTED_BLOCK_RE.finditer(content):
        # Regular HTML before the protected block is translated normally.
        result.append(
            _replace_phrases_in_html(content[last : block.start()], sources, phrases)
        )
        result.append(
            _replace_phrases_in_protected_block(block.group(0), sources, phrases)
        )
        last = block.end()
    result.append(_replace_phrases_in_html(content[last:], sources, phrases))
    return "".join(result)


def _replace_phrases_in_html(
    segment: str, sources: list[str], phrases: dict[str, Any]
) -> str:
    if not segment:
        return segment
    for source in sources:
        segment = segment.replace(source, phrases[source])
    return segment


def _replace_phrases_in_protected_block(
    block: str, sources: list[str], phrases: dict[str, Any]
) -> str:
    if not _LD_JSON_OPEN_RE.match(block):
        # Executable <script> / <style>: never substitute. User-facing strings in
        # these blocks are localized at runtime via window.FSQR_I18N (see
        # templates/cookie-consent.html), so the Japanese source text is only an
        # inert fallback here.
        return block
    # JSON-LD structured data: still translate, but escape each translation so the
    # embedded JSON stays syntactically valid even when it contains quotes.
    for source in sources:
        block = block.replace(source, _json_string_escape(phrases[source]))
    return block
