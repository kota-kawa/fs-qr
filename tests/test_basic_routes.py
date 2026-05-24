import json
import re
from html.parser import HTMLParser
from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient


def _json_escaped(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)[1:-1]


class VisibleTextScanner(HTMLParser):
    LOCALIZED_ATTRS = {
        "alt",
        "aria-label",
        "content",
        "data-copied-label",
        "data-default-label",
        "placeholder",
        "title",
        "value",
    }
    SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__()
        self._skip_stack = []
        self.values = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_stack.append(tag)
            return
        if self._skip_stack:
            return
        for name, value in attrs:
            if name in self.LOCALIZED_ATTRS and value:
                self.values.append(value)

    def handle_endtag(self, tag):
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()

    def handle_data(self, data):
        if not self._skip_stack and data.strip():
            self.values.append(data.strip())


LOCALIZED_PUBLIC_PATHS = (
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
    "/about",
    "/usage",
    "/contact",
    "/privacy-policy",
    "/site-operator",
    "/articles",
    "/fs-qr-concept",
    "/safe-sharing",
    "/encryption",
    "/business",
    "/education",
    "/risk-mitigation",
)


def test_index(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'action="/search_all"' in response.text
    assert 'aria-label="横断検索"' in response.text
    assert 'placeholder="ルームID"' in response.text
    assert 'placeholder="パスワード"' in response.text


def test_index_uses_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=en"})
    assert response.status_code == 200
    assert 'lang="en"' in response.text
    assert "File Sharing Menu" in response.text
    assert "Settings" in response.text
    assert response.headers["content-language"] == "en"
    assert "Cookie" in response.headers["vary"]


def test_index_uses_simplified_chinese_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=zh-CN"})
    assert response.status_code == 200
    assert 'lang="zh-CN"' in response.text
    assert "文件共享菜单" in response.text
    assert response.headers["content-language"] == "zh-CN"


def test_index_uses_traditional_chinese_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=zh-TW"})
    assert response.status_code == 200
    assert 'lang="zh-TW"' in response.text
    assert "檔案共享選單" in response.text
    assert response.headers["content-language"] == "zh-TW"


def test_index_uses_korean_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=ko"})
    assert response.status_code == 200
    assert 'lang="ko"' in response.text
    assert "파일 공유 메뉴" in response.text
    assert response.headers["content-language"] == "ko"


def test_index_accepts_every_supported_language_cookie(test_client: TestClient):
    from i18n import SUPPORTED_LANGUAGES

    for language in SUPPORTED_LANGUAGES:
        response = test_client.get("/", headers={"Cookie": f"fsqr_language={language}"})
        assert response.status_code == 200
        assert f'lang="{language}"' in response.text
        assert response.headers["content-language"] == language


def test_settings_language_switcher_exposes_every_supported_language(
    test_client: TestClient,
):
    from i18n import SUPPORTED_LANGUAGES

    response = test_client.get("/")
    assert response.status_code == 200

    for language in SUPPORTED_LANGUAGES:
        assert f'value="{language}"' in response.text
        assert f'data-value="{language}"' in response.text


def test_index_localizes_language_option_labels_for_english(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=en"})
    assert response.status_code == 200
    assert ">Japanese<" in response.text
    assert ">Chinese (Simplified)<" in response.text
    assert ">Chinese (Traditional)<" in response.text
    assert ">Korean<" in response.text
    assert "日本語" not in response.text


def test_note_page_uses_translated_editor_helper_text(test_client: TestClient):
    response = test_client.get("/note", headers={"Cookie": "fsqr_language=en"})
    assert response.status_code == 200
    assert "Shared note (up to 10000 characters)" in response.text
    assert "You can enter up to 10000 characters." in response.text
    assert "最大10000文字まで入力可能です。" not in response.text


def test_fsqr_upload_page_uses_translated_upload_limit_hint(test_client: TestClient):
    response = test_client.get("/fs-qr", headers={"Cookie": "fsqr_language=en"})
    assert response.status_code == 200
    assert "* You can upload up to 10 files, with a total of 500 MB." in response.text
    assert "※最大10ファイル、合計500MBまで扱えます。" not in response.text


def test_retention_preview_message_is_translated_for_english(test_client: TestClient):
    for path in ("/fs-qr", "/create_room", "/create_note_room"):
        response = test_client.get(path, headers={"Cookie": "fsqr_language=en"})
        assert response.status_code == 200
        assert "Will be automatically deleted around {time}" in response.text
        assert "ごろに自動削除されます" not in response.text
        assert _json_escaped("ごろに自動削除されます") not in response.text


def test_retention_preview_message_is_translated_for_chinese(test_client: TestClient):
    translated = "将在 {time} 左右自动删除"
    for path in ("/fs-qr", "/create_room", "/create_note_room"):
        response = test_client.get(path, headers={"Cookie": "fsqr_language=zh-CN"})
        assert response.status_code == 200
        assert translated in response.text or _json_escaped(translated) in response.text
        assert "ごろに自動削除されます" not in response.text
        assert _json_escaped("ごろに自動削除されます") not in response.text


@pytest.mark.parametrize(
    ("language", "japanese_pattern"),
    [
        ("en", re.compile(r"[ぁ-んァ-ヶ一-龠々ー]")),
        ("zh-CN", re.compile(r"[ぁ-んァ-ヶ々ー]")),
        ("zh-TW", re.compile(r"[ぁ-んァ-ヶ々ー]")),
        ("ko", re.compile(r"[ぁ-んァ-ヶ一-龠々ー]")),
    ],
)
def test_localized_public_pages_do_not_render_japanese_text(
    test_client: TestClient, language: str, japanese_pattern: re.Pattern
):
    for path in LOCALIZED_PUBLIC_PATHS:
        response = test_client.get(f"{path}?lang={language}")
        assert response.status_code == 200, path
        assert response.headers["content-language"] == language

        scanner = VisibleTextScanner()
        scanner.feed(response.text)
        leaks = [
            " ".join(value.split())
            for value in scanner.values
            if japanese_pattern.search(value)
        ]
        assert leaks == [], f"{path} leaked Japanese text: {leaks[:3]}"


def test_about(test_client: TestClient):
    response = test_client.get("/about")
    assert response.status_code == 200


def test_usage(test_client: TestClient):
    response = test_client.get("/usage")
    assert response.status_code == 200


def test_contact(test_client: TestClient):
    response = test_client.get("/contact")
    assert response.status_code == 200


def test_privacy_policy(test_client: TestClient):
    response = test_client.get("/privacy-policy")
    assert response.status_code == 200
    assert "IP Geolocation by DB-IP" in response.text


def test_site_operator(test_client: TestClient):
    response = test_client.get("/site-operator")
    assert response.status_code == 200


def test_404(test_client: TestClient):
    response = test_client.get("/non-existent-page")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]


def test_session_middleware_order():
    from app import app

    class_names = [middleware.cls.__name__ for middleware in app.user_middleware]
    session_index = next(
        i for i, name in enumerate(class_names) if "SessionMiddleware" in name
    )
    autoload_index = next(
        i for i, name in enumerate(class_names) if "SessionAutoloadMiddleware" in name
    )
    assert session_index < autoload_index


def test_search_all_fsqr_single_match_redirects(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit", AsyncMock(return_value=(True, None, None))
        ),
        patch(
            "top_search.fsqr_data.get_data_by_credentials",
            AsyncMock(return_value=[{"secure_id": "abc123-uid-file"}]),
        ),
        patch("top_search.group_data.pich_room_id", AsyncMock(return_value=None)),
        patch("top_search.note_data.pick_room_id", AsyncMock(return_value=None)),
        patch("top_search.register_success", AsyncMock()),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/download/abc123-uid-file"


def test_search_all_group_single_match_redirects(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit", AsyncMock(return_value=(True, None, None))
        ),
        patch(
            "top_search.fsqr_data.get_data_by_credentials", AsyncMock(return_value=[])
        ),
        patch("top_search.group_data.pich_room_id", AsyncMock(return_value="abc123")),
        patch(
            "top_search.get_room_if_active", AsyncMock(return_value={"id": "abc123"})
        ),
        patch("top_search.note_data.pick_room_id", AsyncMock(return_value=None)),
        patch("top_search.register_success", AsyncMock()),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/group/r/abc123"


def test_search_all_note_single_match_redirects(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit", AsyncMock(return_value=(True, None, None))
        ),
        patch(
            "top_search.fsqr_data.get_data_by_credentials", AsyncMock(return_value=[])
        ),
        patch("top_search.group_data.pich_room_id", AsyncMock(return_value=None)),
        patch("top_search.note_data.pick_room_id", AsyncMock(return_value="abc123")),
        patch(
            "top_search.note_data.get_room_meta_direct",
            AsyncMock(return_value={"id": "abc123"}),
        ),
        patch("top_search.register_success", AsyncMock()),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/note/r/abc123"


def test_search_all_multiple_matches_returns_choice_page(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit", AsyncMock(return_value=(True, None, None))
        ),
        patch(
            "top_search.fsqr_data.get_data_by_credentials",
            AsyncMock(return_value=[{"secure_id": "abc123-uid-file"}]),
        ),
        patch("top_search.group_data.pich_room_id", AsyncMock(return_value="abc123")),
        patch(
            "top_search.get_room_if_active", AsyncMock(return_value={"id": "abc123"})
        ),
        patch("top_search.note_data.pick_room_id", AsyncMock(return_value=None)),
        patch("top_search.register_success", AsyncMock()),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 200
    assert "noindex, nofollow" in response.text
    assert "FSQR" in response.text
    assert "Group" in response.text


def test_search_all_no_match_returns_404(test_client: TestClient):
    with (
        patch(
            "top_search.check_rate_limit", AsyncMock(return_value=(True, None, None))
        ),
        patch(
            "top_search.fsqr_data.get_data_by_credentials", AsyncMock(return_value=[])
        ),
        patch("top_search.group_data.pich_room_id", AsyncMock(return_value=None)),
        patch("top_search.note_data.pick_room_id", AsyncMock(return_value=None)),
        patch("top_search.register_failure", AsyncMock(return_value=(None, None))),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 404
    assert "見つかりません" in response.text


def test_search_all_invalid_input_returns_400(test_client: TestClient):
    with patch(
        "top_search.check_rate_limit",
        new_callable=AsyncMock,
        return_value=(True, None, None),
    ):
        response = test_client.post(
            "/search_all", data={"id": "bad!!", "password": "654321"}
        )

    assert response.status_code == 400
    assert "ID" in response.text


def test_search_all_rate_limited_returns_429(test_client: TestClient):
    with patch(
        "top_search.check_rate_limit",
        new_callable=AsyncMock,
        return_value=(False, None, "30分"),
    ):
        response = test_client.post(
            "/search_all", data={"id": "abc123", "password": "654321"}
        )

    assert response.status_code == 429
    assert "30分" in response.text
