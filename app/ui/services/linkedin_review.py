from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import crud
from app.services.linkedin_review_actions import approve_staged_row_create_contact


def approve_reviewed_staging_row(
    *,
    db: Session,
    staging_row_id: int,
    organisation_id: int | None,
    reviewer: str | None,
):
    row = crud.get_linkedin_connection_staging_row(db, staging_row_id)
    if not row:
        raise HTTPException(status_code=404, detail="LinkedIn staging row not found")

    target_organisation_id = row.matched_organisation_id or organisation_id
    if not target_organisation_id:
        raise HTTPException(status_code=400, detail="No resolved target organisation for this row")

    organisation = crud.get_organisation(db, target_organisation_id)
    if not organisation:
        raise HTTPException(status_code=400, detail="Selected organisation not found")

    crud.update_linkedin_connection_staging_row(
        db,
        staging_row_id,
        {
            "matched_organisation_id": target_organisation_id,
            "matched_organisation_name": organisation.name,
            "review_notes": getattr(row, "review_notes", None),
        },
    )

    approve_staged_row_create_contact(
        db=db,
        staged_row_id=staging_row_id,
        organisation_id=target_organisation_id,
        reviewer=reviewer,
    )

    return {
        "staging_row_id": staging_row_id,
        "organisation_id": target_organisation_id,
    }