from starlette.testclient import TestClient

def test_articles_index(test_client: TestClient):
    response = test_client.get("/articles")
    assert response.status_code == 200

def test_fs_qr_concept(test_client: TestClient):
    response = test_client.get("/fs-qr-concept")
    assert response.status_code == 200

def test_safe_sharing(test_client: TestClient):
    response = test_client.get("/safe-sharing")
    assert response.status_code == 200

def test_encryption(test_client: TestClient):
    response = test_client.get("/encryption")
    assert response.status_code == 200

def test_education(test_client: TestClient):
    response = test_client.get("/education")
    assert response.status_code == 200

def test_business(test_client: TestClient):
    response = test_client.get("/business")
    assert response.status_code == 200

def test_risk_mitigation(test_client: TestClient):
    response = test_client.get("/risk-mitigation")
    assert response.status_code == 200
