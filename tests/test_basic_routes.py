from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient


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
    "/task_menu",
    "/task",
    "/create_task_room",
    "/search_task",
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


def test_index_ignores_non_japanese_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=en"})
    assert response.status_code == 200
    assert 'lang="ja"' in response.text
    assert "ファイル共有メニュー" in response.text
    assert "設定" in response.text
    assert response.headers["content-language"] == "ja"
    assert "Cookie" in response.headers["vary"]


def test_index_uses_simplified_chinese_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=zh-CN"})
    assert response.status_code == 200
    assert 'lang="ja"' in response.text
    assert "ファイル共有メニュー" in response.text
    assert response.headers["content-language"] == "ja"


def test_index_uses_traditional_chinese_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=zh-TW"})
    assert response.status_code == 200
    assert 'lang="ja"' in response.text
    assert "ファイル共有メニュー" in response.text
    assert response.headers["content-language"] == "ja"


def test_index_uses_korean_language_cookie(test_client: TestClient):
    response = test_client.get("/", headers={"Cookie": "fsqr_language=ko"})
    assert response.status_code == 200
    assert 'lang="ja"' in response.text
    assert "ファイル共有メニュー" in response.text
    assert response.headers["content-language"] == "ja"


def test_index_uses_japanese_for_every_supported_language_cookie(
    test_client: TestClient,
):
    from i18n import SUPPORTED_LANGUAGES

    for language in SUPPORTED_LANGUAGES:
        response = test_client.get("/", headers={"Cookie": f"fsqr_language={language}"})
        assert response.status_code == 200
        assert 'lang="ja"' in response.text
        assert response.headers["content-language"] == "ja"


def test_settings_language_switcher_is_temporarily_japanese_only(
    test_client: TestClient,
):
    response = test_client.get("/")
    assert response.status_code == 200
    assert 'value="ja"' in response.text
    assert 'data-value="ja"' in response.text
    assert 'value="en"' not in response.text
    assert 'data-value="en"' not in response.text


def test_index_uses_native_language_labels_regardless_of_ui_language(
    test_client: TestClient,
):
    # 言語ドロップダウンは現在のUI言語に関わらず、各言語をその言語自身の
    # 名称（自称名）で統一表示する。英語UIでも日本語は「日本語」、
    # 韓国語は「한국어」のように表示され、表示内容が言語ごとに変わらない。
    for cookie_lang in ("en", "ja", "ko"):
        response = test_client.get(
            "/", headers={"Cookie": f"fsqr_language={cookie_lang}"}
        )
        assert response.status_code == 200
        assert ">日本語<" in response.text
        assert ">English<" not in response.text
        assert ">简体中文<" not in response.text
        assert ">繁體中文<" not in response.text
        assert ">한국어<" not in response.text


def test_note_page_stays_japanese_during_review(test_client: TestClient):
    response = test_client.get("/note", headers={"Cookie": "fsqr_language=en"})
    assert response.status_code == 200
    assert "共有ノート（最大10000文字）" in response.text
    assert "最大10000文字まで入力可能です。" in response.text
    assert "Shared note (up to 10000 characters)" not in response.text


def test_fsqr_upload_page_stays_japanese_during_review(test_client: TestClient):
    response = test_client.get("/fs-qr", headers={"Cookie": "fsqr_language=en"})
    assert response.status_code == 200
    assert "※最大30ファイル、合計1024MBまでアップロードできます。" in response.text
    assert (
        "* You can upload up to 30 files, totaling up to 1024 MB." not in response.text
    )


def test_retention_preview_message_stays_japanese_during_review(
    test_client: TestClient,
):
    for path in ("/create_room", "/create_note_room"):
        response = test_client.get(path, headers={"Cookie": "fsqr_language=en"})
        assert response.status_code == 200
        assert r"\u81ea\u52d5\u524a\u9664\u3055\u308c\u307e\u3059" in response.text
        assert "Will be automatically deleted around {time}" not in response.text


def test_retention_preview_message_stays_japanese_for_chinese_cookie(
    test_client: TestClient,
):
    for path in ("/create_room", "/create_note_room"):
        response = test_client.get(path, headers={"Cookie": "fsqr_language=zh-CN"})
        assert response.status_code == 200
        assert r"\u81ea\u52d5\u524a\u9664\u3055\u308c\u307e\u3059" in response.text
        assert "将在 {time} 左右自动删除" not in response.text


@pytest.mark.parametrize("language", ["en", "zh-CN", "zh-TW", "ko"])
def test_non_japanese_language_queries_are_redirected(
    test_client: TestClient, language: str
):
    for path in LOCALIZED_PUBLIC_PATHS:
        response = test_client.get(f"{path}?lang={language}")
        assert response.status_code == 301, path
        assert response.headers["location"].endswith(path)


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
    assert 'datetime="2026-07-17">2026-07-17</time>' in response.text


def test_google_tags_are_loaded_through_cookie_consent(test_client: TestClient):
    for path in ("/about", "/usage"):
        response = test_client.get(path)
        assert response.status_code == 200
        assert "window.FSQR_TAGS" in response.text
        assert 'googleAnalyticsId: "G-D26D8ZXKNV"' in response.text
        assert 'adsenseClientId: "ca-pub-4557554518872474"' in response.text
        assert 'src="https://www.googletagmanager.com/gtag/js' not in response.text
        assert (
            'src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            not in response.text
        )


ADSENSE_ACCOUNT_META = (
    '<meta name="google-adsense-account" content="ca-pub-4557554518872474">'
)


def test_adsense_account_meta_tag_is_kept_only_on_public_content(
    test_client: TestClient,
):
    for path in ("/", "/about", "/usage", "/articles"):
        response = test_client.get(path)
        assert response.status_code == 200
        assert ADSENSE_ACCOUNT_META in response.text


def test_adsense_is_not_exposed_on_functional_pages(test_client: TestClient):
    for path in (
        "/fs-qr",
        "/group",
        "/create_room",
        "/note",
        "/create_note_room",
        "/search_note",
        "/task",
        "/create_task_room",
        "/search_task",
    ):
        response = test_client.get(path)
        assert response.status_code == 200
        assert "window.FSQR_TAGS" in response.text
        assert 'googleAnalyticsId: "G-D26D8ZXKNV"' in response.text
        # ツール画面には AdSense のメタタグ・クライアント ID を出さない。
        assert "adsenseClientId" not in response.text
        assert 'class="adsbygoogle"' not in response.text
        assert "ca-pub-4557554518872474" not in response.text
        assert ADSENSE_ACCOUNT_META not in response.text
        assert 'src="https://www.googletagmanager.com/gtag/js' not in response.text
        assert (
            'src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
            not in response.text
        )


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
