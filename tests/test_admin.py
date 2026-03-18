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
