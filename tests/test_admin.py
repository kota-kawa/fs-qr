import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient


def test_admin_list_no_auth(test_client: TestClient):
    """パスワードなしアクセスはエラーページ (200) を返す"""
    response = test_client.get("/admin/list")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_admin_list_wrong_pw(test_client: TestClient):
    """誤ったパスワードでアクセスするとエラーページ (200) を返す"""
    response = test_client.get("/admin/list?pw=wrongpassword")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_admin_remove_wrong_pw(test_client: TestClient):
    """誤ったパスワードで削除エンドポイントにアクセスするとエラーページ (200) を返す"""
    response = test_client.post(
        "/admin/remove/somesecureid", data={"pw": "wrongpassword"}
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- /all-remove: 誤ったパスワード → エラーページ ---


def test_all_remove_wrong_pw(test_client: TestClient):
    """誤ったパスワードで全削除リクエストを送るとエラーページ (200) を返す"""
    response = test_client.post("/all-remove", data={"pw": "wrongpassword"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- /admin/remove/{secure_id}: secure_id が存在しない → エラーページ ---


def test_admin_remove_not_found(test_client: TestClient):
    """正しいパスワードでも secure_id が存在しない場合はエラーページ (200) を返す"""
    with (
        patch("Admin.admin_app.ADMIN_KEY", "test_master_key"),
        patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None),
    ):
        response = test_client.post(
            "/admin/remove/nonexistent", data={"pw": "test_master_key"}
        )
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


# --- /admin/file/{secure_id}: db_admin ルート ---


def test_db_admin_file_detail_wrong_pw(test_client):
    """誤ったパスワードでは 403 を返す"""
    response = test_client.get("/admin/file/abc123?pw=wrongpw")
    assert response.status_code == 403
    assert response.json()["error"] == "forbidden"


def test_db_admin_file_detail_not_found(test_client):
    """正しいパスワードでも secure_id が存在しない場合は 404 を返す"""
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None),
    ):
        response = test_client.get("/admin/file/nonexistent?pw=testpw")
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_db_admin_file_detail_found(test_client):
    """正しいパスワードで secure_id が存在する場合は 200 JSON を返す"""
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
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch(
            "FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=mock_data
        ),
    ):
        response = test_client.get("/admin/file/abc123-uid-file?pw=testpw")

    assert response.status_code == 200
    data = response.json()
    assert data["secure_id"] == "abc123-uid-file"
    assert data["id"] == "abc123"
    assert "files" in data


# --- /admin/room/{room_id}: db_admin ルート ---


def test_db_admin_room_detail_wrong_pw(test_client):
    """誤ったパスワードでは 403 を返す"""
    response = test_client.get("/admin/room/abc123?pw=wrongpw")
    assert response.status_code == 403


def test_db_admin_room_detail_not_found(test_client):
    """正しいパスワードでも room_id が存在しない場合は 404 を返す"""
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch("Group.group_data.get_data", new_callable=AsyncMock, return_value=None),
    ):
        response = test_client.get("/admin/room/nonexistent?pw=testpw")
    assert response.status_code == 404


def test_db_admin_room_detail_found(test_client):
    """正しいパスワードで room_id が存在する場合は 200 JSON を返す"""
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
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch(
            "Group.group_data.get_data", new_callable=AsyncMock, return_value=mock_data
        ),
    ):
        response = test_client.get("/admin/room/abc123?pw=testpw")

    assert response.status_code == 200
    data = response.json()
    assert data["room_id"] == "abc123"
    assert "files" in data


# --- POST /admin/: ダッシュボードフォーム ---


def test_db_admin_dashboard_post_redirects(test_client):
    """POST /admin/ はパスワードをクエリパラメータに含むリダイレクトを返す"""
    response = test_client.post("/admin/", data={"password": "testpw"})
    assert response.status_code == 302
    assert "pw=" in response.headers["location"]


def test_db_admin_dashboard_get_unauthenticated(test_client):
    """GET /admin/ で誤ったパスワードは未認証ページ (200) を返す"""
    response = test_client.get("/admin/?pw=wrongpw")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_db_admin_dashboard_get_authenticated(test_client):
    """GET /admin/ で正しいパスワードはダッシュボード (200) を返す"""
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch("Admin.db_admin.safe_count", new_callable=AsyncMock, return_value=0),
        patch("Admin.db_admin.safe_recent", new_callable=AsyncMock, return_value=[]),
    ):
        response = test_client.get("/admin/?pw=testpw")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# --- /admin/file/{secure_id}/download ---


def test_db_admin_file_download_wrong_pw(test_client):
    """誤ったパスワードでは 403 を返す"""
    response = test_client.get("/admin/file/abc123/download?pw=wrongpw")
    assert response.status_code == 403


def test_db_admin_file_download_not_found(test_client):
    """secure_id が存在しない場合は 404 を返す"""
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch("FSQR.fsqr_data.get_data", new_callable=AsyncMock, return_value=None),
    ):
        response = test_client.get("/admin/file/nonexistent/download?pw=testpw")
    assert response.status_code == 404


# --- /admin/room/{room_id}/download ---


def test_db_admin_room_download_wrong_pw(test_client):
    """誤ったパスワードでは 403 を返す"""
    response = test_client.get("/admin/room/abc123/download?pw=wrongpw")
    assert response.status_code == 403


def test_db_admin_room_download_not_found(test_client):
    """room_id が存在しない場合は 404 を返す"""
    with (
        patch("Admin.db_admin.ADMIN_DB_PW", "testpw"),
        patch("Group.group_data.get_data", new_callable=AsyncMock, return_value=None),
    ):
        response = test_client.get("/admin/room/nonexistent/download?pw=testpw")
    assert response.status_code == 404
