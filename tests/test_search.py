from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_search_empty():
    response = client.get("/search?query=a")
    assert response.status_code == 200


def test_search_invalid():
    response = client.get("/search?query=")
    assert response.status_code == 200