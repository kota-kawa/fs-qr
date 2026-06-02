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
    response = test_client.post(
        "/search_note_process",
        data={"id": "bad!!", "password": "123456"},
    )
    assert response.status_code == 400


def test_search_note_invalid_password_chars(test_client: TestClient):
    response = test_client.post(
        "/search_note_process",
        data={"id": "abc123", "password": "abc"},
    )
    assert response.status_code == 400


# --- note_room: ルームが見つからない → 404 ---


def test_note_room_not_found(test_client: TestClient):
    """旧形式のルームURLは停止済みなので 410 を返す"""
    response = test_client.get("/note/abc123/000000")
    assert response.status_code == 410


def test_note_room_injects_realtime_limits_into_config(test_client: TestClient):
    """note_room はリアルタイム設定に制限値を含める"""
    from datetime import datetime

    mock_meta = {
        "id": "tester",
        "retention_days": 7,
        "time": None,
        "expires_at": datetime(2026, 1, 8, 0, 0, 0),
    }
    mock_row = {
        "content": "",
        "updated_at": datetime(2026, 1, 1, 0, 0, 0),
        "version": 0,
    }
    with (
        patch(
            "Note.note_app.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch("Note.note_app.has_note_room_access", return_value=True),
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            return_value=mock_meta,
        ),
        patch(
            "Note.note_app.nd.get_row", new_callable=AsyncMock, return_value=mock_row
        ),
        patch("Note.note_app.register_success", new_callable=AsyncMock),
    ):
        response = test_client.get("/note/r/abc123")
    assert response.status_code == 200
    html = response.text
    assert (
        "window.__FSQR_APP__.api.setConfig('noteRoomRealtime', Object.freeze({" in html
    )
    assert "maxContentLength" in html
    assert "selfEditTimeoutMs" in html
    assert "mergeStatus" in html
    assert 'id="noteShareQrCode"' in html
    assert 'data-share-url=""' in html
    assert "/static/qrcode.min.js" in html
    assert "api.qrserver.com" not in html


def test_note_share_entry_renders_room_without_redirect(test_client: TestClient):
    """QRの共有URLはスマホのブラウザ移動で壊れないよう直接ルームを表示する"""
    from datetime import datetime

    share_token = "note-share-token-1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    mock_meta = {
        "id": "tester",
        "retention_days": 7,
        "expires_at": datetime(2026, 1, 8, 0, 0, 0),
    }
    mock_row = {
        "content": "",
        "updated_at": datetime(2026, 1, 1, 0, 0, 0),
        "version": 0,
    }
    with (
        patch(
            "Note.note_app.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "Note.note_app.resolve_share_link",
            new_callable=AsyncMock,
            return_value={
                "service_key": "note",
                "resource_id": "not999",
                "metadata": {"id": "not999", "password": "024680"},
            },
        ),
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            return_value=mock_meta,
        ),
        patch(
            "Note.note_app.nd.get_row", new_callable=AsyncMock, return_value=mock_row
        ),
        patch("Note.note_app.register_success", new_callable=AsyncMock),
    ):
        response = test_client.get(f"/note/s/{share_token}")

    assert response.status_code == 200
    assert "location" not in response.headers
    html = response.text
    assert "リアルタイムノート" in html
    assert f'data-share-url="http://testserver/note/s/{share_token}"' in html
    # 共有URLで入った受信者にもパスワードが表示される
    assert "024680" in html


def test_note_direct_not_found(test_client: TestClient):
    """note_direct_access は停止済みなので 410 を返す"""
    response = test_client.get("/note_direct/abc123/000000")
    assert response.status_code == 410


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


def test_create_note_room_generates_numeric_password(test_client: TestClient):
    create_mock = AsyncMock()
    with (
        patch("Note.note_app.generate_room_password", return_value="000042"),
        patch("Note.note_app.secrets.token_urlsafe", return_value="Strong_pw1"),
        patch(
            "Note.note_app._room_id_exists", new_callable=AsyncMock, return_value=False
        ),
        patch("Note.note_app.nd.create_room", create_mock),
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            return_value={"id": "abc123"},
        ),
    ):
        response = test_client.post(
            "/create_note_room",
            json={"id": "abc123", "idMode": "manual"},
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/note/r/abc123"
    create_mock.assert_awaited_once_with("abc123", "000042", "abc123", retention_days=7)


def test_note_owner_session_can_delete_room(test_client: TestClient):
    """ルーム作成直後の同一セッションだけNoteルームを削除できる"""
    from datetime import datetime

    room_id = "ndel01"
    meta = {
        "id": room_id,
        "retention_days": 7,
        "expires_at": datetime(2026, 1, 8, 0, 0, 0),
    }
    remove_mock = AsyncMock()
    with (
        patch("Note.note_app.generate_room_password", return_value="000042"),
        patch(
            "Note.note_app._room_id_exists", new_callable=AsyncMock, return_value=False
        ),
        patch("Note.note_app.nd.create_room", new_callable=AsyncMock),
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            side_effect=[meta, meta],
        ),
        patch("Note.note_app.nd.remove_room", remove_mock),
        patch(
            "Note.note_app.note_ws_hub.broadcast", new_callable=AsyncMock
        ) as broadcast_mock,
        patch(
            "Note.note_app.publish_room_expired", new_callable=AsyncMock
        ) as publish_mock,
        patch(
            "Note.note_app.note_ws_hub.close_room", new_callable=AsyncMock
        ) as close_mock,
    ):
        create_response = test_client.post(
            "/create_note_room",
            json={"id": room_id, "idMode": "manual"},
        )
        delete_response = test_client.post(f"/note/r/{room_id}/delete")

    assert create_response.status_code == 302
    assert delete_response.status_code == 302
    assert delete_response.headers["location"] == "/remove-succes"
    remove_mock.assert_awaited_once_with(room_id)
    broadcast_mock.assert_awaited_once()
    publish_mock.assert_awaited_once_with(room_id)
    close_mock.assert_awaited_once_with(room_id)


def test_note_delete_room_requires_owner_session(test_client: TestClient):
    """作成セッションがないNoteルーム削除は403を返す"""
    from datetime import datetime

    room_id = "nfor01"
    meta = {
        "id": room_id,
        "retention_days": 7,
        "expires_at": datetime(2026, 1, 8, 0, 0, 0),
    }
    with (
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            return_value=meta,
        ),
        patch("Note.note_app.nd.remove_room", new_callable=AsyncMock) as remove_mock,
    ):
        response = test_client.post(f"/note/r/{room_id}/delete")

    assert response.status_code == 403
    remove_mock.assert_not_awaited()


def test_create_note_room_fetch_returns_redirect_url(test_client: TestClient):
    """fetch からの作成は画面遷移先を JSON で返す"""
    create_mock = AsyncMock()
    with (
        patch("Note.note_app.generate_room_password", return_value="000042"),
        patch("Note.note_app.secrets.token_urlsafe", return_value="Strong_pw1"),
        patch(
            "Note.note_app._room_id_exists", new_callable=AsyncMock, return_value=False
        ),
        patch("Note.note_app.nd.create_room", create_mock),
        patch(
            "Note.note_app._get_room_if_valid",
            new_callable=AsyncMock,
            return_value={"id": "abc123"},
        ),
    ):
        response = test_client.post(
            "/create_note_room",
            data={"id": "abc123", "idMode": "manual", "retention_days": "7"},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["redirect_url"] == "/note/r/abc123"
    assert payload["data"]["share_url"] == "http://testserver/note/s/Strong_pw1"
    assert payload["data"]["password"] == "000042"
    create_mock.assert_awaited_once_with("abc123", "000042", "abc123", retention_days=7)


def test_create_note_room_room_check_error_returns_json(test_client: TestClient):
    """ID 確認でDB例外が起きたら fetch が読める JSON エラーを返す"""
    with (
        patch("Note.note_app.secrets.token_urlsafe", return_value="Strong_pw1"),
        patch(
            "Note.note_app._room_id_exists",
            new_callable=AsyncMock,
            side_effect=Exception("missing table"),
        ),
    ):
        response = test_client.post(
            "/create_note_room",
            data={"id": "abc123", "idMode": "manual", "retention_days": "7"},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")


def test_create_note_room_db_error_returns_json(test_client: TestClient):
    """DB 例外でも fetch が読める JSON エラーを返す"""
    with (
        patch("Note.note_app.secrets.token_urlsafe", return_value="Strong_pw1"),
        patch(
            "Note.note_app._room_id_exists", new_callable=AsyncMock, return_value=False
        ),
        patch(
            "Note.note_app.nd.create_room",
            new_callable=AsyncMock,
            side_effect=Exception("database unavailable"),
        ),
    ):
        response = test_client.post(
            "/create_note_room",
            data={"id": "abc123", "idMode": "manual", "retention_days": "7"},
            headers={"X-Requested-With": "fetch", "Accept": "application/json"},
        )

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["status"] == "error"
    assert (
        payload["error"] == "ルーム作成に失敗しました。時間をおいて再度お試しください。"
    )


# --- Note API: GET /api/note/{room_id} ---


def test_note_api_get_not_found(test_client: TestClient):
    """存在しない/期限切れルームへの GET は 410 を返す"""
    with (
        patch("Note.note_api.has_note_room_access", return_value=True),
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = test_client.get("/api/note/abc123")
    assert response.status_code == 410
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_note_api_get_found_returns_content(test_client: TestClient):
    """ルームが存在する場合はコンテンツと更新日時を返す"""
    from datetime import datetime

    mock_row = {
        "content": "Hello, World!",
        "updated_at": datetime(2026, 1, 1, 0, 0, 0, 0),
        "version": 0,
    }
    with (
        patch("Note.note_api.has_note_room_access", return_value=True),
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value={"room_id": "abc123", "expires_at": datetime(2026, 1, 8)},
        ),
        patch(
            "Note.note_data.get_row",
            new_callable=AsyncMock,
            return_value=mock_row,
        ),
    ):
        response = test_client.get("/api/note/abc123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["content"] == "Hello, World!"
    assert "updated_at" in payload["data"]
    assert payload["data"]["version"] == 0


def test_note_api_get_uninitialized_room_returns_404(test_client: TestClient):
    """updated_at が None のルームは 410 を返す"""
    mock_row = {"content": "", "updated_at": None}
    with (
        patch("Note.note_api.has_note_room_access", return_value=True),
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
        response = test_client.get("/api/note/abc123")

    assert response.status_code == 410


# --- Note API: POST /api/note/{room_id} ---


def test_note_api_post_not_found(test_client: TestClient):
    """存在しない/期限切れルームへの POST は 410 を返す"""
    with (
        patch("Note.note_api.has_note_room_access", return_value=True),
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        response = test_client.post(
            "/api/note/abc123",
            json={"content": "test", "base_version": 0, "original_content": ""},
        )
    assert response.status_code == 410


def test_note_api_post_content_too_long_returns_400(test_client: TestClient):
    """コンテンツが最大長を超える場合は 400 を返す"""
    from Note.note_sync import MAX_CONTENT_LENGTH

    long_content = "x" * (MAX_CONTENT_LENGTH + 1)
    with (
        patch("Note.note_api.has_note_room_access", return_value=True),
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value={"room_id": "abc123"},
        ),
    ):
        response = test_client.post(
            "/api/note/abc123",
            json={
                "content": long_content,
                "base_version": 0,
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
        "version": 1,
    }
    with (
        patch("Note.note_api.has_note_room_access", return_value=True),
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
            "/api/note/abc123",
            json={
                "content": "new content",
                "base_version": 0,
                "original_content": "original",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["note_status"] == "ok"
    assert payload["data"]["version"] == 1


def test_note_api_post_rejects_missing_sync_params(test_client: TestClient):
    """base_version が未指定の POST は 400 を返す"""
    with (
        patch("Note.note_api.has_note_room_access", return_value=True),
        patch(
            "Note.note_data.get_room_meta_direct",
            new_callable=AsyncMock,
            return_value={"room_id": "abc123"},
        ),
    ):
        response = test_client.post(
            "/api/note/abc123",
            json={"content": "some content"},
        )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"


def test_note_legacy_api_returns_410(test_client: TestClient):
    response = test_client.get("/api/note/abc123/000000")
    assert response.status_code == 410
