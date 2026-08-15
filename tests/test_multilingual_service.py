from __future__ import annotations

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
    "/task_menu",
    "/task",
    "/create_task_room",
    "/search_task",
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
    "Task",
}


def _assert_japanese_service_response(response, path: str) -> None:
    assert response.status_code == 200, path
    assert "text/html" in response.headers["content-type"], path
    assert response.headers["content-language"] == "ja", path

    html_tag = HTML_TAG_RE.search(response.text)
    assert html_tag, f"{path}: missing <html> tag"

    assert 'lang="ja"' in html_tag.group(0), path
    assert 'dir="ltr"' in html_tag.group(0), path

    # The cookie/settings component must receive the same locale that rendered
    # the page, otherwise client-side language switching can drift from the HTML.
    assert 'language: "ja"' in response.text, path
    assert 'value="ja"' in response.text, path
    assert 'data-value="ja"' in response.text, path
    assert 'value="en"' not in response.text, path
    assert 'data-value="en"' not in response.text, path
    _assert_no_cross_script_leakage(response.text, "ja", path)


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
def test_service_pages_are_japanese_only_during_review(
    test_client: TestClient, path: str
):
    _assert_japanese_service_response(test_client.get(path), path)


@pytest.mark.parametrize("language", ["en-US", "zh-hant", "zh_hans", "kr", "ar-SA"])
def test_non_japanese_language_aliases_are_suspended(
    test_client: TestClient, language: str
):
    response = test_client.get(f"/fs-qr?lang={language}")

    assert response.status_code == 301
    assert response.headers["location"].endswith("/fs-qr")
