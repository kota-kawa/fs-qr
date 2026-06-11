from __future__ import annotations

import json
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


HTML_TAG_RE = re.compile(r"<html[^>]*>", re.IGNORECASE)
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
    "Japanese kana": re.compile(r"[\u3040-\u30ff]"),
    "CJK": re.compile(r"[\u3400-\u9fff]"),
    "Hangul": re.compile(r"[\u1100-\u11ff\uac00-\ud7af]"),
    "Thai": re.compile(r"[\u0e00-\u0e7f]"),
    "Arabic": re.compile(r"[\u0600-\u06ff]"),
    "Devanagari": re.compile(r"[\u0904-\u0939\u0958-\u0961\u0970-\u097f]"),
    "Bengali": re.compile(r"[\u0980-\u09ff]"),
    "Cyrillic": re.compile(r"[\u0400-\u04ff]"),
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


def _assert_localized_service_response(response, language: str, path: str) -> None:
    assert response.status_code == 200, f"{path}?lang={language}"
    assert "text/html" in response.headers["content-type"], f"{path}?lang={language}"
    assert response.headers["content-language"] == language, f"{path}?lang={language}"

    html_tag = HTML_TAG_RE.search(response.text)
    assert html_tag, f"{path}?lang={language}: missing <html> tag"

    expected_dir = "rtl" if language == "ar" else "ltr"
    assert f'lang="{language}"' in html_tag.group(0), f"{path}?lang={language}"
    assert f'dir="{expected_dir}"' in html_tag.group(0), f"{path}?lang={language}"

    # The cookie/settings component must receive the same locale that rendered
    # the page, otherwise client-side language switching can drift from the HTML.
    assert f"language: {json.dumps(language)}" in response.text, (
        f"{path}?lang={language}"
    )
    assert f'value="{language}"' in response.text, f"{path}?lang={language}"
    assert f'data-value="{language}"' in response.text, f"{path}?lang={language}"
    _assert_no_cross_script_leakage(response.text, language, path)


def _user_facing_segments(html: str) -> list[str]:
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


def _assert_no_cross_script_leakage(html: str, language: str, path: str) -> None:
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

    assert leaks == [], (
        f"{path}?lang={language} contains text from another script:\n"
        + "\n".join(leaks[:20])
    )


@pytest.mark.parametrize("path", SERVICE_SMOKE_PATHS)
def test_multilingual_service_pages_render_for_every_supported_language(
    test_client: TestClient, path: str
):
    from i18n import SUPPORTED_LANGUAGES

    for language in SUPPORTED_LANGUAGES:
        response = test_client.get(f"{path}?lang={language}")

        _assert_localized_service_response(response, language, path)


@pytest.mark.parametrize(
    ("language", "expected_lang", "expected_dir"),
    [
        ("en-US", "en", "ltr"),
        ("zh-hant", "zh-TW", "ltr"),
        ("zh_hans", "zh-CN", "ltr"),
        ("kr", "ko", "ltr"),
        ("ar-SA", "ar", "rtl"),
    ],
)
def test_multilingual_service_accepts_common_language_aliases(
    test_client: TestClient, language: str, expected_lang: str, expected_dir: str
):
    response = test_client.get(f"/fs-qr?lang={language}")

    assert response.status_code == 200
    assert response.headers["content-language"] == expected_lang
    html_tag = HTML_TAG_RE.search(response.text)
    assert html_tag
    assert f'lang="{expected_lang}"' in html_tag.group(0)
    assert f'dir="{expected_dir}"' in html_tag.group(0)
