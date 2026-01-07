from starlette.testclient import TestClient

def test_group_menu(test_client: TestClient):
    response = test_client.get("/group_menu")
    assert response.status_code == 200

def test_group_access_page(test_client: TestClient):
    response = test_client.get("/group")
    assert response.status_code == 200

def test_create_room_page(test_client: TestClient):
    response = test_client.get("/create_room")
    assert response.status_code == 200

def test_search_group_page(test_client: TestClient):
    response = test_client.get("/search_group")
    assert response.status_code == 200
