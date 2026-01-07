from starlette.testclient import TestClient

def test_admin_list_no_auth(test_client: TestClient):
    # パスワードなしでアクセスしても、エラーページが返るがステータスコードは200(または設定次第)のはず
    # アプリがクラッシュしないことを確認する
    response = test_client.get("/admin/list")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
