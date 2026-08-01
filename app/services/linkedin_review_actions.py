from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db import models
from app.services.task_recommendations import create_task_if_needed


def approve_staged_row_create_contact(
    db: Session,
    staged_row_id: int,
    organisation_id: int,
    reviewer: str | None = None,
):
    staged_row = (
        db.query(models.LinkedInConnectionStaging)
        .filter(models.LinkedInConnectionStaging.id == staged_row_id)
        .first()
    )
    if not staged_row:
        raise ValueError("LinkedIn staging row not found")

    organisation = (
        db.query(models.Organisation)
        .filter(models.Organisation.id == organisation_id)
        .first()
    )
    if not organisation:
        raise ValueError("Organisation not found")

    existing_contact = (
        db.query(models.Contact)
        .filter(models.Contact.organisation_id == organisation.id)
        .filter(models.Contact.full_name.ilike(staged_row.full_name_raw))
        .first()
    )
    if existing_contact:
        staged_row.matched_contact_id = existing_contact.id
        staged_row.matched_organisation_id = organisation.id
        staged_row.match_status = "review_matched_existing"
        staged_row.match_confidence = 0.90
        staged_row.review_status = "approved"
        staged_row.review_notes = f"Reviewer matched to existing contact under organisation {organisation.name}"
        staged_row.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(staged_row)
        return staged_row, existing_contact, False

    contact = models.Contact(
        organisation_id=organisation.id,
        first_name=staged_row.first_name,
        last_name=staged_row.last_name,
        full_name=staged_row.full_name_raw,
        email=staged_row.email,
        source_type="linkedin",
        linkedin_profile_url=staged_row.linkedin_profile_url,
        linkedin_connection_status="connected",
        verification_status="review_approved",
        organisation_name=organisation.name,
    )
    db.add(contact)
    db.flush()

    staged_row.matched_contact_id = contact.id
    staged_row.matched_organisation_id = organisation.id
    staged_row.match_status = "review_created"
    staged_row.match_confidence = 0.90
    staged_row.review_status = "approved"
    staged_row.review_notes = f"Reviewer approved create under organisation {organisation.name}"
    staged_row.processed_at = datetime.now(timezone.utc)

    activity = models.Activity(
        contact_id=contact.id,
        organisation_id=organisation.id,
        activity_type="linkedin_connection_review_approved",
        activity_date=datetime.now(timezone.utc),
        outcome="LinkedIn connection approved from review queue",
        notes=f"Approved from LinkedIn review for import run {staged_row.import_run_id}",
        logged_by=reviewer or "system",
    )
    db.add(activity)
    db.flush()

    create_task_if_needed(
        db,
        contact_id=contact.id,
        organisation_id=organisation.id,
        project_id=None,
        activity_id=activity.id,
        task_type="Follow up LinkedIn connection",
        reason="Reviewer approved LinkedIn connection; follow-up recommended.",
        rule_name="linkedin_review_approved_followup",
        owner=reviewer,
    )

    db.commit()
    db.refresh(staged_row)
    db.refresh(contact)
    return staged_row, contact, True


def skip_staged_row(
    db: Session,
    staged_row_id: int,
    reviewer: str | None = None,
    note: str | None = None,
):
    staged_row = (
        db.query(models.LinkedInConnectionStaging)
        .filter(models.LinkedInConnectionStaging.id == staged_row_id)
        .first()
    )
    if not staged_row:
        raise ValueError("LinkedIn staging row not found")

    staged_row.review_status = "skipped"
    staged_row.match_status = "review_skipped"
    staged_row.review_notes = note or f"Skipped by {reviewer or 'reviewer'}"
    staged_row.processed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(staged_row)
    return staged_row