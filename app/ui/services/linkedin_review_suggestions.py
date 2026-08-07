from dataclasses import dataclass
from typing import Any


@dataclass
class LinkedInReviewSuggestion:
    organisation_id: int | None
    organisation_name: str | None
    confidence: float
    rationale: str
    source: str


def suggest_target_organisation(
    *,
    staged_row: Any,
    candidate_organisations: list[Any],
) -> LinkedInReviewSuggestion:
    matched_id = getattr(staged_row, "matched_organisation_id", None)
    matched_name = getattr(staged_row, "matched_organisation_name", None)

    if matched_id and matched_name:
        return LinkedInReviewSuggestion(
            organisation_id=matched_id,
            organisation_name=matched_name,
            confidence=0.95,
            rationale="Existing matched organisation already present on the staged row.",
            source="rule",
        )

    return LinkedInReviewSuggestion(
        organisation_id=None,
        organisation_name=None,
        confidence=0.0,
        rationale="No deterministic suggestion available yet.",
        source="rule",
    )