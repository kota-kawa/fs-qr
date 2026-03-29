from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


def test_note_menu(test_client: TestClient):
    response = test_client.get("/note_menu")
    assert response.status_code == 200


def test_create_note_room_page(test_client: TestClient):
    response = test_client.get("/create_note_room")
    assert response.status_code == 200


def test_note_access_page(test_client: TestClient):
    response = test_client.get("/note")
    assert response.status_code == 200


def test_search_note_page(test_client: TestClient):
    response = test_client.get("/search_note")
    assert response.status_code == 200


# --- create_note_room バリデーション (manual モード) ---


def test_create_note_room_empty_id_manual(test_client: TestClient):
    """manual モードで ID が空の場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_note_room",
        json={"id": "", "idMode": "manual"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_create_note_room_invalid_chars(test_client: TestClient):
    """ID に無効な文字が含まれると 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_note_room",
        json={"id": "abc!@#", "idMode": "manual"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_create_note_room_wrong_length(test_client: TestClient):
    """ID が 6 文字でない場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/create_note_room",
        json={"id": "abcde", "idMode": "manual"},  # 5文字
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


# --- search_note_process バリデーション ---


def test_search_note_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字があると /search_note にリダイレクトする"""
    response = test_client.post(
        "/search_note_process",
        data={"id": "bad!!", "password": "123456"},
    )
    # バリデーションエラー時は /search_note へリダイレクト (302)
    assert response.status_code == 302
    assert "/search_note" in response.headers["location"]


def test_search_note_invalid_password_chars(test_client: TestClient):
    """パスワードに英字が含まれると /search_note にリダイレクトする"""
    response = test_client.post(
        "/search_note_process",
        data={"id": "abc123", "password": "abc"},
    )
    assert response.status_code == 302
    assert "/search_note" in response.headers["location"]


# --- note_room: ルームが見つからない → 404 ---


def test_note_room_not_found(test_client: TestClient):
    """認証情報が一致しないルームアクセスは 404 を返す"""
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "Note.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = test_client.get("/note/abc123/000000")
    assert response.status_code == 404


def test_note_room_injects_realtime_limits_into_config(test_client: TestClient):
    """note_room はリアルタイム設定に制限値を含める"""
    mock_meta = {"id": "tester", "retention_days": 7, "time": None}
    with (
        patch(
            "Note.note_app.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            return_value=mock_meta,
        ),
        patch("Note.note_app.register_success", new_callable=AsyncMock),
    ):
        response = test_client.get("/note/abc123/000000")
    assert response.status_code == 200
    html = response.text
    assert "window.__FSQR_APP__.api.setConfig('noteRoomRealtime', Object.freeze({" in html
    assert "maxContentLength" in html
    assert "selfEditTimeoutMs" in html
    assert "mergeStatus" in html


def test_note_direct_not_found(test_client: TestClient):
    """note_direct_access で認証失敗の場合は 404 を返す"""
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "Note.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = test_client.get("/note_direct/abc123/000000")
    assert response.status_code == 404


# --- create_note_room: auto モードで渡した ID が重複 → 409 ---


def test_create_note_room_auto_duplicate(test_client: TestClient):
    """auto モードで渡した ID が既存ルームと重複する場合は 409 を返す"""
    with patch(
        "Note.note_app._room_id_exists",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = test_client.post(
            "/create_note_room",
            json={"id": "abc123", "idMode": "auto"},
        )
    assert response.status_code == 409
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["data"]["retry_auto"] is True


# --- Note API: GET /api/note/{room_id}/{password} ---


def test_note_api_get_not_found(test_client: TestClient):
    """存在しないルームへの GET は 404 を返す"""
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "Note.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = test_client.get("/api/note/abc123/000000")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_note_api_get_found_returns_content(test_client: TestClient):
    """ルームが存在する場合はコンテンツと更新日時を返す"""
    from datetime import datetime

    mock_row = {
        "content": "Hello, World!",
        "updated_at": datetime(2026, 1, 1, 0, 0, 0, 0),
    }
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value={"room_id": "abc123"},
        ),
        patch(
            "Note.note_data.get_row",
            new_callable=AsyncMock,
            return_value=mock_row,
        ),
    ):
        response = test_client.get("/api/note/abc123/000000")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["content"] == "Hello, World!"
    assert "updated_at" in payload["data"]


def test_note_api_get_uninitialized_room_returns_404(test_client: TestClient):
    """updated_at が None のルームは 404 を返す"""
    mock_row = {"content": "", "updated_at": None}
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value={"room_id": "abc123"},
        ),
        patch(
            "Note.note_data.get_row",
            new_callable=AsyncMock,
            return_value=mock_row,
        ),
    ):
        response = test_client.get("/api/note/abc123/000000")

    assert response.status_code == 404


# --- Note API: POST /api/note/{room_id}/{password} ---


def test_note_api_post_not_found(test_client: TestClient):
    """存在しないルームへの POST は 404 を返す"""
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "Note.note_data.pick_room_id_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = test_client.post(
            "/api/note/abc123/000000",
            json={"content": "test"},
        )
    assert response.status_code == 404


def test_note_api_post_content_too_long_returns_400(test_client: TestClient):
    """コンテンツが最大長を超える場合は 400 を返す"""
    from Note.note_sync import MAX_CONTENT_LENGTH

    long_content = "x" * (MAX_CONTENT_LENGTH + 1)
    with patch(
        "Note.note_data.get_room_meta_direct",
        new_callable=AsyncMock,
        return_value={"room_id": "abc123"},
    ):
        response = test_client.post(
            "/api/note/abc123/000000",
            json={
                "content": long_content,
                "last_known_updated_at": "2026-01-01",
                "original_content": "",
            },
        )
    assert response.status_code == 400


def test_note_api_post_success_returns_ok(test_client: TestClient):
    """正常な POST は status=ok を返す"""
    from datetime import datetime

    mock_row = {
        "content": "new content",
        "updated_at": datetime(2026, 1, 1, 0, 0, 0, 0),
    }
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value={"room_id": "abc123"},
        ),
        patch(
            "Note.note_data.save_content",
            new_callable=AsyncMock,
            return_value=1,
        ),
        patch(
            "Note.note_data.get_row",
            new_callable=AsyncMock,
            return_value=mock_row,
        ),
    ):
        response = test_client.post(
            "/api/note/abc123/000000",
            json={
                "content": "new content",
                "last_known_updated_at": "2026-01-01 00:00:00.000000",
                "original_content": "original",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["note_status"] == "ok"


def test_note_api_post_fallback_when_no_sync_params(test_client: TestClient):
    """last_known_updated_at が未指定の POST は ok_unconditional_fallback を返す"""
    from datetime import datetime

    mock_row = {
        "content": "saved",
        "updated_at": datetime(2026, 1, 1, 0, 0, 0, 0),
    }
    with (
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value={"room_id": "abc123"},
        ),
        patch(
            "Note.note_data.save_content",
            new_callable=AsyncMock,
        ),
        patch(
            "Note.note_data.get_row",
            new_callable=AsyncMock,
            return_value=mock_row,
        ),
    ):
        response = test_client.post(
            "/api/note/abc123/000000",
            json={"content": "some content"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["note_status"] == "ok_unconditional_fallback"
