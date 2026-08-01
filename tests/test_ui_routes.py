from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ui_home_loads():
    response = client.get("/ui/")
    assert response.status_code == 200


def test_crm_home_loads():
    response = client.get("/ui/crm")
    assert response.status_code == 200


def test_linkedin_review_page_loads():
    response = client.get("/ui/linkedin/review")
    assert response.status_code == 200


def test_tasks_page_loads():
    response = client.get("/ui/tasks")
    assert response.status_code == 200