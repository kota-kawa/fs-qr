from pathlib import Path
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


def test_all_remove_recreates_upload_dir_when_missing(
    test_client: TestClient, tmp_path: Path
):
    with (
        patch("Admin.admin_app.BASE_DIR", str(tmp_path)),
        patch("Admin.admin_app.ADMIN_KEY", "secret"),
        patch("Admin.admin_app.fs_data.all_remove", new=AsyncMock()),
    ):
        response = test_client.post("/all-remove", data={"pw": "secret"})

    assert response.status_code == 302
    assert (tmp_path / "static" / "upload").is_dir()
