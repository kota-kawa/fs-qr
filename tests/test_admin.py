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
    response = test_client.get("/admin/remove/somesecureid?pw=wrongpassword")
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
        response = test_client.get("/admin/remove/nonexistent?pw=test_master_key")
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

    with patch("Admin.db_admin.table_exists", new_callable=AsyncMock, return_value=True):
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
