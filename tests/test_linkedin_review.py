from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.main import app
from app.ui.core import get_db

client = TestClient(app)


def override_db():
    yield object()


def test_review_approve_redirects_when_valid(monkeypatch):
    app.dependency_overrides[get_db] = override_db

    from app.ui.routes import linkedin as linkedin_routes

    approve_service_mock = Mock()
    monkeypatch.setattr(
        linkedin_routes,
        "approve_reviewed_staging_row",
        approve_service_mock,
    )

    response = client.post(
        "/ui/linkedin/review/123/approve",
        data={"organisation_id": "42", "reviewer": "test"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/linkedin/review"

    approve_service_mock.assert_called_once()
    kwargs = approve_service_mock.call_args.kwargs
    assert kwargs["staging_row_id"] == 123
    assert kwargs["organisation_id"] == 42
    assert kwargs["reviewer"] == "test"

    app.dependency_overrides.clear()