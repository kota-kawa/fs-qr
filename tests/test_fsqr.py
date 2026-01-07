from starlette.testclient import TestClient

def test_fsqr_menu(test_client: TestClient):
    response = test_client.get("/fs-qr_menu")
    assert response.status_code == 200

def test_fsqr_upload_page(test_client: TestClient):
    response = test_client.get("/fs-qr")
    assert response.status_code == 200

def test_fsqr_search_page(test_client: TestClient):
    response = test_client.get("/search_fs-qr")
    assert response.status_code == 200
