from starlette.testclient import TestClient

def test_note_menu(test_client: TestClient):
    response = test_client.get("/note_menu")
    assert response.status_code == 200

def test_create_note_room_page(test_client: TestClient):
    response = test_client.get("/create_note_room")
    assert response.status_code == 200

def test_note_access_page(test_client: TestClient):
    response = test_client.get("/note")
    assert response.status_code == 200

def test_search_note_page(test_client: TestClient):
    response = test_client.get("/search_note")
    assert response.status_code == 200
