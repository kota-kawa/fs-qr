"""厳密な多言語言語汚染テスト。
全ページ・全言語で、非許可スクリプト(日本語、中国語など)が混入していないか検証。
"""

import re

import pytest
from starlette.testclient import TestClient


SERVICE_SMOKE_PATHS = (
    "/",
    "/fs-qr_menu",
    "/fs-qr",
    "/search_fs-qr",
    "/group_menu",
    "/group",
    "/create_room",
    "/search_group",
    "/note_menu",
    "/note",
    "/create_note_room",
    "/search_note",
)

SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)
LD_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
LANG_SELECT_LIST_RE = re.compile(
    r"<ul\b[^>]*class=\"[^\"]*\blang-select-list\b[^\"]*\"[^>]*>.*?</ul>",
    re.I | re.S,
)
LANG_SELECT_RE = re.compile(
    r"<select\b[^>]*data-language-select\b[^>]*>.*?</select>", re.I | re.S
)

SCRIPT_PATTERNS = {
    "Japanese kana": re.compile(r"[぀-ヿ]"),
    "CJK": re.compile(r"[㐀-鿿]"),
    "Hangul": re.compile(r"[ᄀ-ᇿ가-힯]"),
    "Thai": re.compile(r"[฀-๿]"),
    "Arabic": re.compile(r"[؀-ۿ]"),
    "Devanagari": re.compile(r"[ऄ-हक़-ॡ॰-ॿ]"),
    "Bengali": re.compile(r"[ঀ-৿]"),
    "Cyrillic": re.compile(r"[Ѐ-ӿ]"),
}

ALLOWED_SCRIPTS_BY_LANGUAGE = {
    "ja": {"Japanese kana", "CJK"},
    "zh-CN": {"CJK"},
    "zh-TW": {"CJK"},
    "ko": {"Hangul"},
    "th": {"Thai"},
    "ar": {"Arabic"},
    "hi": {"Devanagari"},
    "bn": {"Bengali"},
    "ru": {"Cyrillic"},
    "uk": {"Cyrillic"},
}

ALLOWED_SEGMENTS = {
    "FS!QR",
    "Group",
    "Note",
}


def _user_facing_segments(html: str) -> list[str]:
    """Extract user-facing text segments from HTML, excluding scripts, styles, and language selectors."""
    # Remove language selector UI (contains legitimate multilingual labels)
    html = LANG_SELECT_LIST_RE.sub(" ", html)
    html = LANG_SELECT_RE.sub(" ", html)

    ld_strings = []
    for block in LD_RE.findall(html):
        ld_strings.extend(re.findall(r'"((?:[^"\\]|\\.)*)"', block))

    stripped = SCRIPT_STYLE_RE.sub(" ", html)
    stripped = re.sub(r"<!--.*?-->", " ", stripped, flags=re.S)
    attrs = re.findall(
        r'(?:content|alt|title|placeholder|aria-label)="([^"]*)"', stripped
    )
    text = TAG_RE.sub("\n", stripped)
    segments = [s.strip() for s in text.split("\n") if s.strip()]
    return segments + [s.strip() for s in attrs + ld_strings if s.strip()]


def _check_script_leakage(html: str, language: str, path: str) -> list[str]:
    """Check for script/language leakage. Returns list of leaked segments."""
    allowed_scripts = ALLOWED_SCRIPTS_BY_LANGUAGE.get(language, set())
    leaks = []

    for segment in _user_facing_segments(html):
        if segment in ALLOWED_SEGMENTS:
            continue
        for script_name, pattern in SCRIPT_PATTERNS.items():
            if script_name in allowed_scripts:
                continue
            if pattern.search(segment):
                leaks.append(f"{script_name}: {segment[:120]}")
                break

    return leaks


@pytest.mark.parametrize("path", SERVICE_SMOKE_PATHS)
def test_all_pages_render_in_all_languages_without_script_leakage(
    test_client: TestClient, path: str
):
    """Each page × each language must have zero script/language leakage."""
    from i18n import SUPPORTED_LANGUAGES

    for language in SUPPORTED_LANGUAGES:
        response = test_client.get(f"{path}?lang={language}")

        assert response.status_code == 200, f"{path}?lang={language}"
        leaks = _check_script_leakage(response.text, language, path)
        assert leaks == [], (
            f"{path}?lang={language} contains leaked text from another script:\n"
            + "\n".join(leaks[:20])
        )


def test_articles_render_in_all_languages_without_script_leakage(
    test_client: TestClient,
):
    """Sample of articles must render without script leakage in fully translated languages.

    This tests a few representative articles in core supported languages (ja, en, zh-CN, uk)
    to catch gross translation leaks in article content. Full article coverage is tracked
    separately since articles are translated incrementally.
    """
    from Articles.articles_registry import get_all_articles
    from i18n import SUPPORTED_LANGUAGES

    articles = get_all_articles()
    assert len(articles) > 0

    # Sample 5 representative articles
    sample_articles = articles[:: max(1, len(articles) // 5)][:5]
    # Check only in core well-supported languages
    check_languages = [
        lang for lang in SUPPORTED_LANGUAGES if lang in ("ja", "en", "zh-CN", "uk")
    ]

    for article in sample_articles:
        url = "/" + article["slug"]
        for language in check_languages:
            response = test_client.get(f"{url}?lang={language}")

            assert response.status_code == 200, f"{url}?lang={language}"
            leaks = _check_script_leakage(response.text, language, url)
            assert leaks == [], (
                f"{url}?lang={language} contains leaked text from another script:\n"
                + "\n".join(leaks[:20])
            )
