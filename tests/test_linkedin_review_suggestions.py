from types import SimpleNamespace

from app.ui.services.linkedin_review_suggestions import suggest_target_organisation


def test_suggest_target_organisation_uses_existing_match():
    staged_row = SimpleNamespace(
        matched_organisation_id=42,
        matched_organisation_name="Acme Pty Ltd",
    )

    result = suggest_target_organisation(
        staged_row=staged_row,
        candidate_organisations=[],
    )

    assert result.organisation_id == 42
    assert result.organisation_name == "Acme Pty Ltd"
    assert result.confidence == 0.95
    assert result.source == "rule"


def test_suggest_target_organisation_returns_empty_when_no_match():
    staged_row = SimpleNamespace(
        matched_organisation_id=None,
        matched_organisation_name=None,
    )

    result = suggest_target_organisation(
        staged_row=staged_row,
        candidate_organisations=[],
    )

    assert result.organisation_id is None
    assert result.organisation_name is None
    assert result.confidence == 0.0
    assert result.source == "rule"