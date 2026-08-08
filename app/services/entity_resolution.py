from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db import models
from app.services.linkedin_imports import normalize_text
from app.services.org_aliases import load_org_alias_map
from app.services.task_recommendations import create_task_if_needed

AUTO_MATCH_THRESHOLD = 0.95
REVIEW_THRESHOLD = 0.80


def create_entity_match(
    db: Session,
    source_record_type: str,
    source_record_id: int,
    candidate_entity_type: str,
    candidate_entity_id: int,
    score: float,
    method: str,
    review_status: str = "pending",
):
    obj = models.EntityMatch(
        source_record_type=source_record_type,
        source_record_id=source_record_id,
        candidate_entity_type=candidate_entity_type,
        candidate_entity_id=candidate_entity_id,
        match_score=score,
        match_method=method,
        review_status=review_status,
    )
    db.add(obj)
    return obj


def find_organisation_candidates(db: Session, company_name_normalized: str):
    if not company_name_normalized:
        return []

    orgs = db.query(models.Organisation).all()
    alias_map = load_org_alias_map()
    candidates = []

    alias_resolved_name = alias_map.get(company_name_normalized)

    for org in orgs:
        name = normalize_text(org.name)
        short_name = normalize_text(getattr(org, "short_name", None))

        score = 0.0
        method = None

        if company_name_normalized == name:
            score = 1.0
            method = "exact_org_name"
        elif short_name and company_name_normalized == short_name:
            score = 0.98
            method = "exact_short_name"
        elif alias_resolved_name and normalize_text(alias_resolved_name) == name:
            score = 0.99
            method = "alias_map_match"

        if score > 0:
            candidates.append((org, score, method))

    return sorted(candidates, key=lambda x: x[1], reverse=True)


def find_contact_candidates(db: Session, full_name_normalized: str, organisation_id: int | None = None):
    if not full_name_normalized:
        return []

    query = db.query(models.Contact)
    if organisation_id:
        query = query.filter(models.Contact.organisation_id == organisation_id)

    candidates = []
    for contact in query.all():
        candidate_name = normalize_text(contact.full_name)
        score = 0.0
        if candidate_name and candidate_name == full_name_normalized:
            score = 0.96 if organisation_id else 0.82

        if score > 0:
            candidates.append((contact, score, "deterministic_contact_name_match"))

    return sorted(candidates, key=lambda x: x[1], reverse=True)


def process_staged_linkedin_row(db: Session, staged_row):
    org_candidates = find_organisation_candidates(db, staged_row.company_name_normalized)
    best_org = org_candidates[0] if org_candidates else None

    matched_org = None
    if best_org and best_org[1] >= AUTO_MATCH_THRESHOLD:
        matched_org = best_org[0]
        staged_row.matched_organisation_id = matched_org.id

    if not matched_org:
        staged_row.match_status = "ignored_non_target_org"
        staged_row.review_status = "not_required"
        staged_row.match_confidence = 0.0
        staged_row.processed_at = datetime.now(timezone.utc)

        run = (
            db.query(models.LinkedinImportRun)
            .filter(models.LinkedinImportRun.id == staged_row.import_run_id)
            .first()
        )
        if run:
            run.rows_processed = (run.rows_processed or 0) + 1
            run.status = "processed"

        db.commit()
        db.refresh(staged_row)
        return staged_row

    contact_candidates = find_contact_candidates(
        db,
        staged_row.full_name_normalized,
        matched_org.id,
    )
    best_contact = contact_candidates[0] if contact_candidates else None

    if best_contact and best_contact[1] >= AUTO_MATCH_THRESHOLD:
        contact = best_contact[0]
        contact.linkedin_profile_url = contact.linkedin_profile_url or staged_row.linkedin_profile_url
        contact.linkedin_connection_status = "connected"
        if not contact.source_type:
            contact.source_type = "linkedin"

        staged_row.matched_contact_id = contact.id
        staged_row.matched_organisation_id = contact.organisation_id
        staged_row.match_status = "auto_matched"
        staged_row.match_confidence = 0.96
        staged_row.review_status = "not_required"

        activity = models.Activity(
            contact_id=contact.id,
            organisation_id=contact.organisation_id,
            activity_type="linkedin_connection_imported",
            activity_date=datetime.now(timezone.utc),
            outcome="LinkedIn connection imported",
            notes=f"Imported from LinkedIn connections upload run {staged_row.import_run_id}",
            logged_by="system",
        )
        db.add(activity)
        db.flush()

        create_task_if_needed(
            db,
            contact_id=contact.id,
            organisation_id=contact.organisation_id,
            project_id=None,
            activity_id=activity.id,
            task_type="Follow up LinkedIn connection",
            reason="New LinkedIn connection imported; follow-up recommended.",
            rule_name="linkedin_new_connection_followup",
        )

    else:
        likely_duplicate = (
            db.query(models.Contact)
            .filter(models.Contact.organisation_id == matched_org.id)
            .filter(models.Contact.full_name.ilike(staged_row.full_name_raw))
            .first()
        )

        if likely_duplicate:
            staged_row.match_status = "review_required"
            staged_row.review_status = "pending"
            staged_row.match_confidence = 0.85

            create_entity_match(
                db,
                "linkedin_connection_staging",
                staged_row.id,
                "contact",
                likely_duplicate.id,
                0.85,
                "same_name_same_org_duplicate_warning",
                "pending",
            )
        else:
            contact = models.Contact(
                organisation_id=matched_org.id,
                first_name=staged_row.first_name,
                last_name=staged_row.last_name,
                full_name=staged_row.full_name_raw,
                email=staged_row.email,
                source_type="linkedin",
                linkedin_profile_url=staged_row.linkedin_profile_url,
                linkedin_connection_status="connected",
                verification_status="imported",
                organisation_name=matched_org.name,
            )
            db.add(contact)
            db.flush()

            staged_row.matched_contact_id = contact.id
            staged_row.matched_organisation_id = matched_org.id
            staged_row.match_status = "created"
            staged_row.match_confidence = 0.95
            staged_row.review_status = "not_required"

    staged_row.processed_at = datetime.now(timezone.utc)

    run = (
        db.query(models.LinkedinImportRun)
        .filter(models.LinkedinImportRun.id == staged_row.import_run_id)
        .first()
    )
    if run:
        run.rows_processed = (run.rows_processed or 0) + 1

        if staged_row.match_status == "auto_matched":
            run.rows_matched = (run.rows_matched or 0) + 1
        elif staged_row.match_status == "created":
            run.rows_created = (run.rows_created or 0) + 1
        elif staged_row.match_status == "review_required":
            run.rows_flagged = (run.rows_flagged or 0) + 1

        run.status = "processed"

    db.commit()
    db.refresh(staged_row)
    return staged_row