from unittest.mock import AsyncMock, patch

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
