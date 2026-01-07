from starlette.testclient import TestClient

def test_index(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_about(test_client: TestClient):
    response = test_client.get("/about")
    assert response.status_code == 200

def test_usage(test_client: TestClient):
    response = test_client.get("/usage")
    assert response.status_code == 200

def test_contact(test_client: TestClient):
    response = test_client.get("/contact")
    assert response.status_code == 200

def test_privacy_policy(test_client: TestClient):
    response = test_client.get("/privacy-policy")
    assert response.status_code == 200

def test_site_operator(test_client: TestClient):
    response = test_client.get("/site-operator")
    assert response.status_code == 200

def test_404(test_client: TestClient):
    response = test_client.get("/non-existent-page")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
