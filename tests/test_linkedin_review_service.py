from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.ui.services import linkedin_review as service


class DummyRow:
    def __init__(self, matched_organisation_id=None, review_notes=None):
        self.matched_organisation_id = matched_organisation_id
        self.review_notes = review_notes


class DummyOrganisation:
    def __init__(self, organisation_id, name):
        self.id = organisation_id
        self.name = name


def test_approve_reviewed_staging_row_uses_form_organisation_id(monkeypatch):
    db = object()
    update_mock = Mock()
    approve_mock = Mock()

    monkeypatch.setattr(
        service.crud,
        "get_linkedin_connection_staging_row",
        lambda db, row_id: DummyRow(matched_organisation_id=None, review_notes="Needs review"),
    )
    monkeypatch.setattr(
        service.crud,
        "get_organisation",
        lambda db, organisation_id: DummyOrganisation(organisation_id=42, name="Acme Pty Ltd"),
    )
    monkeypatch.setattr(
        service.crud,
        "update_linkedin_connection_staging_row",
        update_mock,
    )
    monkeypatch.setattr(
        service,
        "approve_staged_row_create_contact",
        approve_mock,
    )

    result = service.approve_reviewed_staging_row(
        db=db,
        staging_row_id=123,
        organisation_id=42,
        reviewer="test",
    )

    assert result == {"staging_row_id": 123, "organisation_id": 42}
    update_mock.assert_called_once_with(
        db,
        123,
        {
            "matched_organisation_id": 42,
            "matched_organisation_name": "Acme Pty Ltd",
            "review_notes": "Needs review",
        },
    )
    approve_mock.assert_called_once_with(
        db=db,
        staged_row_id=123,
        organisation_id=42,
        reviewer="test",
    )


def test_approve_reviewed_staging_row_uses_existing_match(monkeypatch):
    db = object()
    update_mock = Mock()
    approve_mock = Mock()

    monkeypatch.setattr(
        service.crud,
        "get_linkedin_connection_staging_row",
        lambda db, row_id: DummyRow(matched_organisation_id=99, review_notes="Auto matched"),
    )
    monkeypatch.setattr(
        service.crud,
        "get_organisation",
        lambda db, organisation_id: DummyOrganisation(organisation_id=99, name="Matched Org"),
    )
    monkeypatch.setattr(
        service.crud,
        "update_linkedin_connection_staging_row",
        update_mock,
    )
    monkeypatch.setattr(
        service,
        "approve_staged_row_create_contact",
        approve_mock,
    )

    result = service.approve_reviewed_staging_row(
        db=db,
        staging_row_id=123,
        organisation_id=42,
        reviewer="test",
    )

    assert result == {"staging_row_id": 123, "organisation_id": 99}
    update_mock.assert_called_once_with(
        db,
        123,
        {
            "matched_organisation_id": 99,
            "matched_organisation_name": "Matched Org",
            "review_notes": "Auto matched",
        },
    )
    approve_mock.assert_called_once_with(
        db=db,
        staged_row_id=123,
        organisation_id=99,
        reviewer="test",
    )


def test_approve_reviewed_staging_row_raises_404_when_row_missing(monkeypatch):
    monkeypatch.setattr(
        service.crud,
        "get_linkedin_connection_staging_row",
        lambda db, row_id: None,
    )

    with pytest.raises(HTTPException) as exc:
        service.approve_reviewed_staging_row(
            db=object(),
            staging_row_id=123,
            organisation_id=42,
            reviewer="test",
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "LinkedIn staging row not found"


def test_approve_reviewed_staging_row_raises_400_when_no_target_org(monkeypatch):
    monkeypatch.setattr(
        service.crud,
        "get_linkedin_connection_staging_row",
        lambda db, row_id: DummyRow(matched_organisation_id=None, review_notes="Needs review"),
    )

    with pytest.raises(HTTPException) as exc:
        service.approve_reviewed_staging_row(
            db=object(),
            staging_row_id=123,
            organisation_id=None,
            reviewer="test",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "No resolved target organisation for this row"


def test_approve_reviewed_staging_row_raises_400_when_org_missing(monkeypatch):
    monkeypatch.setattr(
        service.crud,
        "get_linkedin_connection_staging_row",
        lambda db, row_id: DummyRow(matched_organisation_id=None, review_notes="Needs review"),
    )
    monkeypatch.setattr(
        service.crud,
        "get_organisation",
        lambda db, organisation_id: None,
    )

    with pytest.raises(HTTPException) as exc:
        service.approve_reviewed_staging_row(
            db=object(),
            staging_row_id=123,
            organisation_id=42,
            reviewer="test",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Selected organisation not found"