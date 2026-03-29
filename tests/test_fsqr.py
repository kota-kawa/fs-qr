from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


def test_fsqr_menu(test_client: TestClient):
    response = test_client.get("/fs-qr_menu")
    assert response.status_code == 200


def test_fsqr_upload_page(test_client: TestClient):
    response = test_client.get("/fs-qr")
    assert response.status_code == 200
    html = response.text
    assert "window.__FSQR_APP__.api.setConfig('fsQrUpload', Object.freeze({" in html
    assert "maxFiles" in html
    assert "maxTotalSizeBytes" in html
    assert "maxTotalSizeMB" in html


def test_fsqr_search_page(test_client: TestClient):
    response = test_client.get("/search_fs-qr")
    assert response.status_code == 200


def test_remove_succes_page(test_client: TestClient):
    """削除完了ページが正常に表示される"""
    response = test_client.get("/remove-succes")
    assert response.status_code == 200


# --- アップロードバリデーション ---


def test_upload_no_file(test_client: TestClient):
    """ファイルなしでアップロードすると 400 を返す"""
    response = test_client.post("/upload", data={"name": "", "file_type": "multiple"})
    assert response.status_code == 400


def test_upload_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字が含まれると 400 JSON エラーを返す"""
    response = test_client.post(
        "/upload",
        files={"upfile": ("test.txt", b"hello", "text/plain")},
        data={"name": "inv@lid", "file_type": "multiple"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_upload_wrong_id_length(test_client: TestClient):
    """ID が 6 文字でない場合は 400 JSON エラーを返す"""
    response = test_client.post(
        "/upload",
        files={"upfile": ("test.txt", b"hello", "text/plain")},
        data={"name": "abc", "file_type": "multiple"},  # 3文字
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


def test_upload_too_many_files(test_client: TestClient):
    """ファイル数が 10 を超えると 400 JSON エラーを返す"""
    files = [("upfile", (f"file{i}.txt", b"x", "text/plain")) for i in range(11)]
    response = test_client.post(
        "/upload", files=files, data={"name": "", "file_type": "multiple"}
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["status"] == "error"
    assert isinstance(payload["error"], str)


# --- try_login バリデーション ---


def test_try_login_invalid_id_chars(test_client: TestClient):
    """ID に無効な文字を含む場合はエラーページを返す"""
    response = test_client.post("/try_login", data={"name": "bad!@#", "pw": "123456"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_try_login_invalid_pw_chars(test_client: TestClient):
    """パスワードに英字が混在する場合はエラーページを返す"""
    response = test_client.post("/try_login", data={"name": "abc123", "pw": "abc"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- upload_complete / download の 404 ---


def test_upload_complete_not_found(test_client: TestClient):
    """存在しない secure_id へのアクセスは 404 を返す"""
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None):
        response = test_client.get("/upload_complete/nonexistent000")
    assert response.status_code == 404


def test_download_not_found(test_client: TestClient):
    """存在しない secure_id への download アクセスは 404 を返す"""
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None):
        response = test_client.get("/download/nonexistent000")
    assert response.status_code == 404


def test_download_found_redirects(test_client: TestClient):
    """secure_id に対応するデータが存在する場合は 302 でルームへリダイレクトする"""
    mock_data = [{"id": "abc123", "password": "654321"}]
    with patch(
        "FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=mock_data
    ):
        response = test_client.get("/download/abc123-uid-file.zip")
    assert response.status_code == 302


# --- fs_qr_room: 認証失敗 → 404 ---


def test_fs_qr_room_not_found(test_client: TestClient):
    """認証情報が一致しないルームアクセスは 404 を返す"""
    with patch(
        "FSQR.fsqr_data.get_data_by_credentials",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = test_client.get("/fs-qr/abc123/000000")
    assert response.status_code == 404


# --- try_login: DB 不一致 → エラーページ ---


def test_try_login_not_found(test_client: TestClient):
    """正しい形式でも DB が不一致の場合はエラーページ (200) を返す"""
    with patch("FSQR.fsqr_data.try_login", new_callable=AsyncMock, return_value=False):
        response = test_client.post(
            "/try_login", data={"name": "abc123", "pw": "654321"}
        )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_try_login_success_redirects(test_client: TestClient):
    """認証成功時は 302 でルームページへリダイレクトする"""
    with patch(
        "FSQR.fsqr_data.try_login",
        new_callable=AsyncMock,
        return_value="abc123-uid-file",
    ):
        response = test_client.post(
            "/try_login", data={"name": "abc123", "pw": "654321"}
        )
    assert response.status_code == 302


# --- upload_complete: データが存在する場合 → 200 ---


def test_upload_complete_found(test_client: TestClient):
    """secure_id に対応するデータが存在する場合は 200 を返す"""
    from datetime import datetime

    mock_data = [
        {
            "id": "abc123",
            "password": "654321",
            "retention_days": 7,
            "time": datetime(2026, 1, 1, 0, 0),
        }
    ]
    with patch(
        "FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=mock_data
    ):
        response = test_client.get("/upload_complete/abc123-uid-file")
    assert response.status_code == 200


# --- fs_qr_room: 認証成功 → 200 ---


def test_fs_qr_room_found_returns_200(test_client: TestClient):
    """認証成功でルームページ (200) を表示する"""
    from datetime import datetime

    mock_data = [
        {
            "id": "abc123",
            "password": "654321",
            "secure_id": "abc123-uid-file",
            "retention_days": 7,
            "time": datetime(2026, 1, 1),
        }
    ]
    with (
        patch(
            "FSQR.fsqr_app.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "FSQR.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=mock_data,
        ),
        patch("FSQR.fsqr_app.register_success", new_callable=AsyncMock),
    ):
        response = test_client.get("/fs-qr/abc123/654321")
    assert response.status_code == 200


def test_fs_qr_room_rate_limited_returns_429(test_client: TestClient):
    """レートリミット超過で 429 を返す"""
    with patch(
        "FSQR.fsqr_app.check_rate_limit",
        new_callable=AsyncMock,
        return_value=(False, None, "1日"),
    ):
        response = test_client.get("/fs-qr/abc123/654321")
    assert response.status_code == 429


def test_fs_qr_room_auth_fail_then_blocked_returns_429(test_client: TestClient):
    """認証失敗後にブロック判定で 429 を返す"""
    with (
        patch(
            "FSQR.fsqr_app.check_rate_limit",
            new_callable=AsyncMock,
            return_value=(True, None, None),
        ),
        patch(
            "FSQR.fsqr_data.get_data_by_credentials",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "FSQR.fsqr_app.register_failure",
            new_callable=AsyncMock,
            return_value=(None, "30分"),
        ),
    ):
        response = test_client.get("/fs-qr/abc123/654321")
    assert response.status_code == 429


# --- try_login: レートリミット超過 → 429 ---


def test_try_login_rate_limited_returns_429(test_client: TestClient):
    """try_login でレートリミット超過の場合は 429 を返す"""
    with patch(
        "FSQR.fsqr_app.check_rate_limit",
        new_callable=AsyncMock,
        return_value=(False, None, "30分"),
    ):
        response = test_client.post(
            "/try_login", data={"name": "abc123", "pw": "654321"}
        )
    assert response.status_code == 429
