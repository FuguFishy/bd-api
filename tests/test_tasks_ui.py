from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app
from app.ui.core import get_db

client = TestClient(app)


def override_db():
    yield object()


def test_tasks_page_returns_200(monkeypatch):
    app.dependency_overrides[get_db] = override_db

    from app.ui.routes import tasks as tasks_routes

    today = date.today()
    task_items = [
        SimpleNamespace(id=1, due_date=today - timedelta(days=1), completed_at=None),
        SimpleNamespace(id=2, due_date=today + timedelta(days=3), completed_at=None),
        SimpleNamespace(id=3, due_date=None, completed_at=None),
    ]

    monkeypatch.setattr(tasks_routes.crud, "list_tasks", lambda **kwargs: task_items)
    monkeypatch.setattr(tasks_routes.crud, "list_organisations", lambda db: [])
    monkeypatch.setattr(tasks_routes.crud, "list_contacts", lambda db: [])
    monkeypatch.setattr(tasks_routes.crud, "list_projects", lambda db: [])

    response = client.get("/ui/tasks")

    assert response.status_code == 200
    assert "Tasks" in response.text

    app.dependency_overrides.clear()


def test_task_complete_redirects(monkeypatch):
    app.dependency_overrides[get_db] = override_db

    from app.ui.routes import tasks as tasks_routes

    complete_mock = Mock()
    monkeypatch.setattr(tasks_routes.crud, "complete_task", complete_mock)

    response = client.post("/ui/tasks/99/complete", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/tasks"
    complete_mock.assert_called_once()

    app.dependency_overrides.clear()


def test_tasks_page_passes_filters(monkeypatch):
    app.dependency_overrides[get_db] = override_db

    from app.ui.routes import tasks as tasks_routes

    captured = {}

    def fake_list_tasks(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(tasks_routes.crud, "list_tasks", fake_list_tasks)
    monkeypatch.setattr(tasks_routes.crud, "list_organisations", lambda db: [])
    monkeypatch.setattr(tasks_routes.crud, "list_contacts", lambda db: [])
    monkeypatch.setattr(tasks_routes.crud, "list_projects", lambda db: [])

    response = client.get(
        "/ui/tasks?status=open&organisation_id=7&contact_id=8&project_id=9&include_completed=true"
    )

    assert response.status_code == 200
    assert captured["status"] == "open"
    assert captured["organisation_id"] == 7
    assert captured["contact_id"] == 8
    assert captured["project_id"] == 9
    assert captured["include_completed"] is True

    app.dependency_overrides.clear()