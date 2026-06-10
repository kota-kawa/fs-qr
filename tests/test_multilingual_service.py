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
