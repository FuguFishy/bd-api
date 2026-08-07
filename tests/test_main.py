from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_redirects_to_ui():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/ui/"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}