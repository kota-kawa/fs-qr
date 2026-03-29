import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_admin_sessions(test_client: TestClient):
    test_client.get("/admin/logout")
    test_client.get("/admin/db/logout")


def _login_admin(test_client: TestClient, password: str = "test_master_key"):
    with patch("Admin.admin_app.ADMIN_KEY", password):
        response = test_client.post("/admin/list", data={"pw": password})
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/list"


def _login_db_admin(test_client: TestClient, password: str = "testpw"):
    with patch("Admin.db_admin.ADMIN_DB_PW", password):
        response = test_client.post("/admin/", data={"password": password})
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/"


def test_admin_list_no_auth(test_client: TestClient):
    """未認証アクセスはログインページ (200) を返す"""
    response = test_client.get("/admin/list")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "管理ページログイン" in response.text


def test_admin_list_legacy_query_pw_redirects(test_client: TestClient):
    """旧形式クエリは受け付けず、クリーン URL へ 302 リダイレクトする"""
    response = test_client.get("/admin/list?pw=wrongpassword")
    assert response.status_code == 302
    assert response.headers["location"].endswith("/admin/list")


def test_admin_login_wrong_pw(test_client: TestClient):
    """誤ったパスワードでログインするとログインページを再表示する"""
    with patch("Admin.admin_app.ADMIN_KEY", "test_master_key"):
        response = test_client.post("/admin/list", data={"pw": "wrongpassword"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "マスターパスワードが違います" in response.text


def test_admin_remove_requires_session(test_client: TestClient):
    """未認証で削除エンドポイントにアクセスするとログインへ 302 リダイレクトする"""
    response = test_client.post("/admin/remove/somesecureid")
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/list"


def test_all_remove_requires_session(test_client: TestClient):
    """未認証で全削除リクエストを送るとログインへ 302 リダイレクトする"""
    response = test_client.post("/all-remove")
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/list"


def test_admin_remove_not_found_when_authenticated(test_client: TestClient):
    """ログイン済みで secure_id が存在しない場合はエラーページ (200) を返す"""
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None):
        _login_admin(test_client)
        response = test_client.post("/admin/remove/nonexistent")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_db_admin_safe_count_rejects_unknown_table():
    """想定外テーブル名はSQLを実行せず 0 を返す"""
    from Admin import db_admin

    sess = MagicMock()
    sess.execute = AsyncMock()

    count = asyncio.run(db_admin.safe_count(sess, "fsqr; DROP TABLE fsqr;--"))

    assert count == 0
    sess.execute.assert_not_awaited()


def test_db_admin_safe_recent_rejects_unknown_identifier():
    """想定外の識別子はSQLを実行せず None を返す"""
    from Admin import db_admin

    sess = MagicMock()
    sess.execute = AsyncMock()

    rows = asyncio.run(
        db_admin.safe_recent(
            sess,
            "fsqr",
            "time DESC; DROP TABLE fsqr;--",
        )
    )

    assert rows is None
    sess.execute.assert_not_awaited()


def test_db_admin_safe_recent_uses_parameterized_limit():
    """LIMIT はバインド変数として渡される"""
    from Admin import db_admin

    expected_rows = [{"secure_id": "abc123-uid-file"}]
    result_proxy = MagicMock()
    mapping_result = MagicMock()
    mapping_result.all.return_value = expected_rows
    result_proxy.mappings.return_value = mapping_result

    sess = MagicMock()
    sess.execute = AsyncMock(return_value=result_proxy)
    sess.rollback = AsyncMock()

    with patch(
        "Admin.db_admin.table_exists", new_callable=AsyncMock, return_value=True
    ):
        rows = asyncio.run(db_admin.safe_recent(sess, "fsqr", "time", limit=10))

    assert rows == expected_rows
    sess.execute.assert_awaited_once_with(
        db_admin.RECENT_QUERIES[("fsqr", "time")], {"limit": 10}
    )


def test_db_admin_safe_recent_rejects_invalid_limit():
    """0 以下の LIMIT は拒否する"""
    from Admin import db_admin

    sess = MagicMock()
    sess.execute = AsyncMock()
    sess.rollback = AsyncMock()

    with (
        patch("Admin.db_admin.table_exists", new_callable=AsyncMock, return_value=True),
        pytest.raises(ValueError),
    ):
        asyncio.run(db_admin.safe_recent(sess, "fsqr", "time", limit=0))


def test_db_admin_file_detail_requires_session(test_client):
    """未認証では 403 を返す"""
    response = test_client.get("/admin/file/abc123")
    assert response.status_code == 403
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "forbidden"


def test_db_admin_file_detail_not_found(test_client):
    """認証済みでも secure_id が存在しない場合は 404 を返す"""
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None):
        _login_db_admin(test_client)
        response = test_client.get("/admin/file/nonexistent")
    assert response.status_code == 404
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"] == "not_found"


def test_db_admin_file_detail_found(test_client):
    """認証済みで secure_id が存在する場合は 200 JSON を返す"""
    from datetime import datetime

    mock_data = [
        {
            "secure_id": "abc123-uid-file",
            "id": "abc123",
            "password": "000000",
            "file_type": "multiple",
            "original_filename": "",
            "time": datetime(2026, 1, 1),
        }
    ]
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=mock_data):
        _login_db_admin(test_client)
        response = test_client.get("/admin/file/abc123-uid-file")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["secure_id"] == "abc123-uid-file"
    assert payload["data"]["id"] == "abc123"
    assert "files" in payload["data"]


def test_db_admin_room_detail_requires_session(test_client):
    """未認証では 403 を返す"""
    response = test_client.get("/admin/room/abc123")
    assert response.status_code == 403


def test_db_admin_room_detail_not_found(test_client):
    """認証済みでも room_id が存在しない場合は 404 を返す"""
    with patch("Group.group_data.get_data", new_callable=AsyncMock, return_value=None):
        _login_db_admin(test_client)
        response = test_client.get("/admin/room/nonexistent")
    assert response.status_code == 404


def test_db_admin_room_detail_found(test_client):
    """認証済みで room_id が存在する場合は 200 JSON を返す"""
    from datetime import datetime

    mock_data = [
        {
            "room_id": "abc123",
            "id": "abc123",
            "password": "000000",
            "retention_days": 7,
            "time": datetime(2026, 1, 1),
        }
    ]
    with patch("Group.group_data.get_data", new_callable=AsyncMock, return_value=mock_data):
        _login_db_admin(test_client)
        response = test_client.get("/admin/room/abc123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["room_id"] == "abc123"
    assert "files" in payload["data"]


def test_db_admin_dashboard_post_redirects_without_pw_query(test_client):
    """POST /admin/ はクエリ文字列なしでダッシュボードにリダイレクトする"""
    with patch("Admin.db_admin.ADMIN_DB_PW", "testpw"):
        response = test_client.post("/admin/", data={"password": "testpw"})
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/"


def test_db_admin_dashboard_get_legacy_query_pw_redirects(test_client):
    """GET /admin/?pw=... はクリーン URL へ 302 リダイレクトする"""
    response = test_client.get("/admin/?pw=wrongpw")
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/"


def test_db_admin_dashboard_get_authenticated(test_client):
    """ログイン後の GET /admin/ はダッシュボード (200) を返す"""
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch("Admin.db_admin.safe_count", new_callable=AsyncMock, return_value=0),
        patch("Admin.db_admin.safe_recent", new_callable=AsyncMock, return_value=[]),
    ):
        response_login = test_client.post("/admin/", data={"password": "testpw"})
        assert response_login.status_code == 302
        response = test_client.get("/admin/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_db_admin_file_download_requires_session(test_client):
    """未認証では 403 を返す"""
    response = test_client.get("/admin/file/abc123/download")
    assert response.status_code == 403


def test_db_admin_file_download_not_found(test_client):
    """認証済みで secure_id が存在しない場合は 404 を返す"""
    with patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None):
        _login_db_admin(test_client)
        response = test_client.get("/admin/file/nonexistent/download")
    assert response.status_code == 404


def test_db_admin_room_download_requires_session(test_client):
    """未認証では 403 を返す"""
    response = test_client.get("/admin/room/abc123/download")
    assert response.status_code == 403


def test_db_admin_room_download_not_found(test_client):
    """認証済みで room_id が存在しない場合は 404 を返す"""
    with patch("Group.group_data.get_data", new_callable=AsyncMock, return_value=None):
        _login_db_admin(test_client)
        response = test_client.get("/admin/room/nonexistent/download")
    assert response.status_code == 404
