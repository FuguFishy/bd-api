from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.activities import ActivityCreate
from app.schemas.contacts import ContactCreate
from app.schemas.organisations import OrganisationCreate
from app.schemas.projects import ProjectCreate
from app.schemas.tasks import TaskCreate

BRISBANE_TZ = ZoneInfo("Australia/Brisbane")


def _payload_dict(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_unset=True)
    if isinstance(payload, dict):
        return payload
    raise TypeError("Unsupported payload type")


def _commit_or_raise(
    db: Session,
    duplicate_map: dict[str, str],
    default_message: str,
) -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        message = str(e.orig)

        for constraint, detail in duplicate_map.items():
            if constraint in message:
                raise HTTPException(status_code=409, detail=detail)

        if "ForeignKeyViolation" in message or "violates foreign key constraint" in message:
            raise HTTPException(status_code=400, detail="Referenced record does not exist")

        raise HTTPException(status_code=400, detail=default_message)


def _apply_updates(obj: Any, payload: Any) -> Any:
    values = _payload_dict(payload)
    for key, value in values.items():
        setattr(obj, key, value)
    return obj


def _contact_display_name(contact: Any) -> str:
    first_name = (getattr(contact, "first_name", None) or "").strip()
    last_name = (getattr(contact, "last_name", None) or "").strip()
    full_name = f"{first_name} {last_name}".strip()

    if full_name:
        return full_name

    fallback_full_name = (getattr(contact, "full_name", None) or "").strip()
    if fallback_full_name:
        return fallback_full_name

    return f"Contact {contact.id}"


def _enrich_activities_with_labels(db: Session, activities: list[Any]) -> list[Any]:
    organisation_ids = list(
        {
            activity.organisation_id
            for activity in activities
            if getattr(activity, "organisation_id", None)
        }
    )
    contact_ids = list(
        {
            activity.contact_id
            for activity in activities
            if getattr(activity, "contact_id", None)
        }
    )
    project_ids = list(
        {
            activity.project_id
            for activity in activities
            if getattr(activity, "project_id", None)
        }
    )

    organisation_lookup: dict[int, str] = {}
    if organisation_ids:
        organisation_rows = (
            db.query(models.Organisation)
            .filter(models.Organisation.id.in_(organisation_ids))
            .all()
        )
        organisation_lookup = {
            organisation.id: (organisation.name or f"Organisation {organisation.id}")
            for organisation in organisation_rows
        }

    contact_lookup: dict[int, str] = {}
    if contact_ids:
        contact_rows = (
            db.query(models.Contact)
            .filter(models.Contact.id.in_(contact_ids))
            .all()
        )
        contact_lookup = {
            contact.id: _contact_display_name(contact)
            for contact in contact_rows
        }

    project_lookup: dict[int, str] = {}
    if project_ids:
        project_rows = (
            db.query(models.Project)
            .filter(models.Project.id.in_(project_ids))
            .all()
        )
        project_lookup = {
            project.id: (project.name or f"Project {project.id}")
            for project in project_rows
        }

    for activity in activities:
        activity.organisation_name = organisation_lookup.get(activity.organisation_id)
        activity.contact_label = contact_lookup.get(activity.contact_id)
        activity.project_label = project_lookup.get(activity.project_id)

    return activities


# -------------------------------------------------------------------
# Organisations
# -------------------------------------------------------------------

def create_organisation(db: Session, payload: OrganisationCreate):
    obj = models.Organisation(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(
        db,
        {"organisations_name_key": "Organisation already exists"},
        "Unable to create organisation due to invalid data",
    )
    db.refresh(obj)
    return obj


def list_organisations(
    db: Session,
    q: str | None = None,
    sector: str | None = None,
    tier: str | None = None,
    account_status: str | None = None,
):
    query = db.query(models.Organisation)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Organisation.name.ilike(like),
                models.Organisation.short_name.ilike(like),
            )
        )

    if sector:
        query = query.filter(models.Organisation.sector == sector)
    if tier:
        query = query.filter(models.Organisation.tier == tier)
    if account_status:
        query = query.filter(models.Organisation.account_status == account_status)

    return query.order_by(models.Organisation.name.asc()).all()


def list_organisations_ui(
    db: Session,
    q: str | None = None,
    sector: str | None = None,
    tier: str | None = None,
    account_status: str | None = None,
):
    return list_organisations(
        db=db,
        q=q,
        sector=sector,
        tier=tier,
        account_status=account_status,
    )


def get_organisation(db: Session, organisation_id: int):
    return (
        db.query(models.Organisation)
        .filter(models.Organisation.id == organisation_id)
        .first()
    )


def update_organisation(db: Session, organisation_id: int, payload: dict[str, Any] | Any):
    obj = get_organisation(db, organisation_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Organisation not found")

    _apply_updates(obj, payload)
    _commit_or_raise(
        db,
        {"organisations_name_key": "Organisation already exists"},
        "Unable to update organisation due to invalid data",
    )
    db.refresh(obj)
    return obj


def get_organisation_detail_ui(db: Session, organisation_id: int):
    organisation = get_organisation(db, organisation_id)
    if not organisation:
        return None

    contacts = (
        db.query(models.Contact)
        .filter(models.Contact.organisation_id == organisation_id)
        .order_by(models.Contact.last_name.asc(), models.Contact.first_name.asc())
        .all()
    )

    projects = (
        db.query(models.Project)
        .filter(models.Project.organisation_id == organisation_id)
        .order_by(models.Project.name.asc())
        .all()
    )

    activities = (
        db.query(models.Activity)
        .filter(models.Activity.organisation_id == organisation_id)
        .order_by(models.Activity.activity_date.desc())
        .limit(25)
        .all()
    )
    activities = _enrich_activities_with_labels(db, activities)

    tasks = (
        db.query(models.Task)
        .filter(models.Task.organisation_id == organisation_id)
        .order_by(models.Task.due_date.asc().nullslast(), models.Task.id.desc())
        .limit(25)
        .all()
    )

    return {
        "organisation": organisation,
        "contacts": contacts,
        "projects": projects,
        "activities": activities,
        "tasks": tasks,
    }


# -------------------------------------------------------------------
# Contacts
# -------------------------------------------------------------------

def create_contact(db: Session, payload: ContactCreate):
    obj = models.Contact(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(
        db,
        {
            "contacts_email_key": "Contact email already exists",
        },
        "Unable to create contact due to invalid data",
    )
    db.refresh(obj)
    return obj


def list_contacts(
    db: Session,
    q: str | None = None,
    organisation_id: int | None = None,
):
    query = db.query(models.Contact)

    if organisation_id is not None:
        query = query.filter(models.Contact.organisation_id == organisation_id)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Contact.full_name.ilike(like),
                models.Contact.position_title.ilike(like),
                models.Contact.department.ilike(like),
            )
        )

    contacts = query.order_by(models.Contact.full_name.asc()).all()

    organisation_ids = list(
        {
            contact.organisation_id
            for contact in contacts
            if getattr(contact, "organisation_id", None)
        }
    )

    organisation_lookup: dict[int, str] = {}
    if organisation_ids:
        organisation_rows = (
            db.query(models.Organisation)
            .filter(models.Organisation.id.in_(organisation_ids))
            .all()
        )
        organisation_lookup = {
            organisation.id: (organisation.name or f"Organisation {organisation.id}")
            for organisation in organisation_rows
        }

    for contact in contacts:
        contact.organisation_name = (
            organisation_lookup.get(contact.organisation_id)
            or contact.organisation_name
        )

    return contacts


def get_contact(db: Session, contact_id: int):
    return db.query(models.Contact).filter(models.Contact.id == contact_id).first()


def update_contact(db: Session, contact_id: int, payload: dict[str, Any] | Any):
    obj = get_contact(db, contact_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Contact not found")

    _apply_updates(obj, payload)
    _commit_or_raise(
        db,
        {
            "contacts_email_key": "Contact email already exists",
        },
        "Unable to update contact due to invalid data",
    )
    db.refresh(obj)
    return obj


def get_contact_detail_ui(db: Session, contact_id: int):
    contact = get_contact(db, contact_id)
    if not contact:
        return None

    activities = (
        db.query(models.Activity)
        .filter(models.Activity.contact_id == contact_id)
        .order_by(models.Activity.activity_date.desc())
        .limit(25)
        .all()
    )
    activities = _enrich_activities_with_labels(db, activities)

    tasks = (
        db.query(models.Task)
        .filter(models.Task.contact_id == contact_id)
        .order_by(models.Task.due_date.asc().nullslast(), models.Task.id.desc())
        .limit(25)
        .all()
    )

    projects = (
        db.query(models.Project)
        .filter(models.Project.organisation_id == contact.organisation_id)
        .order_by(models.Project.name.asc())
        .all()
        if getattr(contact, "organisation_id", None)
        else []
    )

    return {
        "contact": contact,
        "activities": activities,
        "tasks": tasks,
        "projects": projects,
    }


# -------------------------------------------------------------------
# Projects
# -------------------------------------------------------------------

def create_project(db: Session, payload: ProjectCreate):
    obj = models.Project(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(
        db,
        {
            "projects_organisation_id_name_key": "Project already exists for this organisation",
            "projects_name_key": "Project already exists",
        },
        "Unable to create project due to invalid data",
    )
    db.refresh(obj)
    return obj


def list_projects(
    db: Session,
    q: str | None = None,
    organisation_id: int | None = None,
    status: str | None = None,
):
    query = db.query(models.Project)

    if organisation_id is not None:
        query = query.filter(models.Project.organisation_id == organisation_id)

    if status:
        query = query.filter(models.Project.status == status)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.Project.name.ilike(like),
                models.Project.project_type.ilike(like),
                models.Project.status.ilike(like),
            )
        )

    return query.order_by(models.Project.name.asc()).all()


def get_project(db: Session, project_id: int):
    return db.query(models.Project).filter(models.Project.id == project_id).first()


def update_project(db: Session, project_id: int, payload: dict[str, Any] | Any):
    obj = get_project(db, project_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Project not found")

    _apply_updates(obj, payload)
    _commit_or_raise(
        db,
        {
            "projects_organisation_id_name_key": "Project already exists for this organisation",
            "projects_name_key": "Project already exists",
        },
        "Unable to update project due to invalid data",
    )
    db.refresh(obj)
    return obj


def get_project_detail_ui(db: Session, project_id: int):
    project = get_project(db, project_id)
    if not project:
        return None

    activities = (
        db.query(models.Activity)
        .filter(models.Activity.project_id == project_id)
        .order_by(models.Activity.activity_date.desc())
        .limit(25)
        .all()
    )
    activities = _enrich_activities_with_labels(db, activities)

    tasks = (
        db.query(models.Task)
        .filter(models.Task.project_id == project_id)
        .order_by(models.Task.due_date.asc().nullslast(), models.Task.id.desc())
        .limit(25)
        .all()
    )

    organisation = None
    if getattr(project, "organisation_id", None):
        organisation = get_organisation(db, project.organisation_id)

    return {
        "project": project,
        "organisation": organisation,
        "activities": activities,
        "tasks": tasks,
    }


# -------------------------------------------------------------------
# Activities
# -------------------------------------------------------------------

def create_activity(db: Session, payload: ActivityCreate):
    obj = models.Activity(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create activity due to invalid data")
    db.refresh(obj)
    return obj


def create_activity_with_optional_task(
    db: Session,
    activity_payload: ActivityCreate | dict[str, Any],
    task_payload: TaskCreate | dict[str, Any] | None = None,
):
    activity = models.Activity(**_payload_dict(activity_payload))
    db.add(activity)

    try:
        db.flush()

        task = None
        if task_payload:
            task_values = _payload_dict(task_payload)
            task_values.setdefault("activity_id", activity.id)
            task = models.Task(**task_values)
            db.add(task)

        db.commit()
        db.refresh(activity)
        if task:
            db.refresh(task)

        return {"activity": activity, "task": task}

    except IntegrityError as e:
        db.rollback()
        message = str(e.orig)

        if "ForeignKeyViolation" in message or "violates foreign key constraint" in message:
            raise HTTPException(status_code=400, detail="Referenced record does not exist")

        raise HTTPException(status_code=400, detail="Unable to create activity due to invalid data")


def list_activities(
    db: Session,
    organisation_id: int | None = None,
    contact_id: int | None = None,
    project_id: int | None = None,
):
    query = db.query(models.Activity)

    if organisation_id is not None:
        query = query.filter(models.Activity.organisation_id == organisation_id)
    if contact_id is not None:
        query = query.filter(models.Activity.contact_id == contact_id)
    if project_id is not None:
        query = query.filter(models.Activity.project_id == project_id)

    activities = query.order_by(models.Activity.activity_date.desc()).all()
    return _enrich_activities_with_labels(db, activities)


def get_activity(db: Session, activity_id: int):
    return db.query(models.Activity).filter(models.Activity.id == activity_id).first()


# -------------------------------------------------------------------
# Tasks
# -------------------------------------------------------------------

def create_task(db: Session, payload: TaskCreate):
    obj = models.Task(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create task due to invalid data")
    db.refresh(obj)
    return obj


def list_tasks(
    db: Session,
    status: str | None = None,
    organisation_id: int | None = None,
    contact_id: int | None = None,
    project_id: int | None = None,
    include_completed: bool = True,
):
    query = db.query(models.Task)

    if organisation_id is not None:
        query = query.filter(models.Task.organisation_id == organisation_id)
    if contact_id is not None:
        query = query.filter(models.Task.contact_id == contact_id)
    if project_id is not None:
        query = query.filter(models.Task.project_id == project_id)

    if status:
        query = query.filter(models.Task.status == status)

    if not include_completed:
        query = query.filter(models.Task.completed_at.is_(None))

    return query.order_by(models.Task.due_date.asc().nullslast(), models.Task.id.desc()).all()


def get_task(db: Session, task_id: int):
    return db.query(models.Task).filter(models.Task.id == task_id).first()


def update_task(db: Session, task_id: int, payload: dict[str, Any] | Any):
    obj = get_task(db, task_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")

    _apply_updates(obj, payload)
    _commit_or_raise(db, {}, "Unable to update task due to invalid data")
    db.refresh(obj)
    return obj


def complete_task(db: Session, task_id: int):
    obj = get_task(db, task_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")

    obj.status = "completed"
    if hasattr(obj, "completed_at"):
        obj.completed_at = datetime.now(timezone.utc)

    _commit_or_raise(db, {}, "Unable to complete task")
    db.refresh(obj)
    return obj


# -------------------------------------------------------------------
# Entity matches
# -------------------------------------------------------------------

def create_entity_match(db: Session, payload: dict[str, Any] | Any):
    obj = models.EntityMatch(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create entity match")
    db.refresh(obj)
    return obj


def list_entity_matches(
    db: Session,
    review_status: str | None = None,
    source_record_type: str | None = None,
    candidate_entity_type: str | None = None,
):
    query = db.query(models.EntityMatch)

    if review_status:
        query = query.filter(models.EntityMatch.review_status == review_status)
    if source_record_type:
        query = query.filter(models.EntityMatch.source_record_type == source_record_type)
    if candidate_entity_type:
        query = query.filter(models.EntityMatch.candidate_entity_type == candidate_entity_type)

    return query.order_by(models.EntityMatch.id.desc()).all()


def get_entity_match(db: Session, entity_match_id: int):
    return (
        db.query(models.EntityMatch)
        .filter(models.EntityMatch.id == entity_match_id)
        .first()
    )


def update_entity_match(db: Session, entity_match_id: int, payload: dict[str, Any] | Any):
    obj = get_entity_match(db, entity_match_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Entity match not found")

    _apply_updates(obj, payload)
    _commit_or_raise(db, {}, "Unable to update entity match")
    db.refresh(obj)
    return obj


def resolve_entity_match(
    db: Session,
    entity_match_id: int,
    review_status: str,
    resolved_by: str | None = None,
    review_notes: str | None = None,
):
    obj = get_entity_match(db, entity_match_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Entity match not found")

    obj.review_status = review_status
    obj.resolved_by = resolved_by
    obj.review_notes = review_notes
    obj.resolved_at = datetime.now(timezone.utc)

    _commit_or_raise(db, {}, "Unable to resolve entity match")
    db.refresh(obj)
    return obj


# -------------------------------------------------------------------
# LinkedIn import runs
# -------------------------------------------------------------------

def create_linkedin_import_run(db: Session, payload: dict[str, Any] | Any):
    obj = models.LinkedinImportRun(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create LinkedIn import run")
    db.refresh(obj)
    return obj


def list_linkedin_import_runs(
    db: Session,
    status: str | None = None,
):
    query = db.query(models.LinkedinImportRun)

    if status:
        query = query.filter(models.LinkedinImportRun.status == status)

    return query.order_by(
        models.LinkedinImportRun.uploaded_at.desc(),
        models.LinkedinImportRun.id.desc(),
    ).all()


def get_linkedin_import_run(db: Session, import_run_id: int):
    return (
        db.query(models.LinkedinImportRun)
        .filter(models.LinkedinImportRun.id == import_run_id)
        .first()
    )


def update_linkedin_import_run(db: Session, import_run_id: int, payload: dict[str, Any] | Any):
    obj = get_linkedin_import_run(db, import_run_id)
    if not obj:
        raise HTTPException(status_code=404, detail="LinkedIn import run not found")

    _apply_updates(obj, payload)
    _commit_or_raise(db, {}, "Unable to update LinkedIn import run")
    db.refresh(obj)
    return obj


def mark_linkedin_import_run_status(
    db: Session,
    import_run_id: int,
    status: str,
    error_summary: str | None = None,
):
    obj = get_linkedin_import_run(db, import_run_id)
    if not obj:
        raise HTTPException(status_code=404, detail="LinkedIn import run not found")

    obj.status = status
    obj.error_summary = error_summary

    if status in {"completed", "failed"} and hasattr(obj, "finished_at"):
        obj.finished_at = datetime.now(timezone.utc)

    _commit_or_raise(db, {}, "Unable to update LinkedIn import run status")
    db.refresh(obj)
    return obj


# -------------------------------------------------------------------
# LinkedIn connection staging
# -------------------------------------------------------------------

def create_linkedin_connection_staging_row(db: Session, payload: dict[str, Any] | Any):
    obj = models.LinkedinConnectionStaging(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(
        db,
        {
            "uq_linkedin_staging_run_rowhash": "Duplicate LinkedIn row for this import run",
        },
        "Unable to create LinkedIn staging row",
    )
    db.refresh(obj)
    return obj


def bulk_create_linkedin_connection_staging_rows(
    db: Session,
    rows: list[dict[str, Any]],
):
    objects = [models.LinkedinConnectionStaging(**row) for row in rows]
    db.add_all(objects)
    _commit_or_raise(
        db,
        {
            "uq_linkedin_staging_run_rowhash": "Duplicate LinkedIn row for this import run",
        },
        "Unable to create LinkedIn staging rows",
    )
    return objects


def list_linkedin_connection_staging_rows(
    db: Session,
    import_run_id: int | None = None,
    match_status: str | None = None,
    review_status: str | None = None,
):
    query = db.query(models.LinkedinConnectionStaging)

    if import_run_id is not None:
        query = query.filter(models.LinkedinConnectionStaging.import_run_id == import_run_id)
    if match_status:
        query = query.filter(models.LinkedinConnectionStaging.match_status == match_status)
    if review_status:
        query = query.filter(models.LinkedinConnectionStaging.review_status == review_status)

    return query.order_by(models.LinkedinConnectionStaging.id.asc()).all()


def list_pending_linkedin_reviews(db: Session):
    return list_linkedin_connection_staging_rows(db, review_status="pending")


def get_linkedin_connection_staging_row(db: Session, staging_row_id: int):
    return (
        db.query(models.LinkedinConnectionStaging)
        .filter(models.LinkedinConnectionStaging.id == staging_row_id)
        .first()
    )


def update_linkedin_connection_staging_row(
    db: Session,
    staging_row_id: int,
    payload: dict[str, Any] | Any,
):
    obj = get_linkedin_connection_staging_row(db, staging_row_id)
    if not obj:
        raise HTTPException(status_code=404, detail="LinkedIn staging row not found")

    _apply_updates(obj, payload)
    _commit_or_raise(db, {}, "Unable to update LinkedIn staging row")
    db.refresh(obj)
    return obj


def mark_linkedin_connection_staging_row_processed(
    db: Session,
    staging_row_id: int,
    match_status: str,
    matched_contact_id: int | None = None,
    matched_organisation_id: int | None = None,
    match_confidence: float | None = None,
    review_status: str | None = None,
    review_notes: str | None = None,
):
    obj = get_linkedin_connection_staging_row(db, staging_row_id)
    if not obj:
        raise HTTPException(status_code=404, detail="LinkedIn staging row not found")

    obj.match_status = match_status
    obj.matched_contact_id = matched_contact_id
    obj.matched_organisation_id = matched_organisation_id
    obj.match_confidence = match_confidence
    obj.processed_at = datetime.now(timezone.utc)

    if review_status is not None:
        obj.review_status = review_status
    if review_notes is not None:
        obj.review_notes = review_notes

    _commit_or_raise(db, {}, "Unable to mark LinkedIn staging row as processed")
    db.refresh(obj)
    return obj


# -------------------------------------------------------------------
# BD Ops dashboard helpers
# -------------------------------------------------------------------

def _workflow_run_to_dict(run: Any) -> dict[str, Any]:
    duration_seconds = None
    if getattr(run, "started_at", None) and getattr(run, "finished_at", None):
        duration_seconds = int((run.finished_at - run.started_at).total_seconds())

    return {
        "id": run.id,
        "workflow_name": run.workflow_name,
        "run_type": getattr(run, "run_type", None),
        "started_at": run.started_at,
        "finished_at": getattr(run, "finished_at", None),
        "status": run.status,
        "records_processed": getattr(run, "records_processed", None),
        "records_flagged": getattr(run, "records_flagged", None),
        "duration_seconds": duration_seconds,
        "error_summary": getattr(run, "error_summary", None),
    }


def _linkedin_import_run_to_dict(run: Any) -> dict[str, Any]:
    duration_seconds = None
    if getattr(run, "uploaded_at", None) and getattr(run, "finished_at", None):
        duration_seconds = int((run.finished_at - run.uploaded_at).total_seconds())

    return {
        "id": run.id,
        "filename": run.filename,
        "uploaded_by": getattr(run, "uploaded_by", None),
        "uploaded_at": run.uploaded_at,
        "finished_at": getattr(run, "finished_at", None),
        "status": run.status,
        "rows_received": getattr(run, "rows_received", None),
        "rows_processed": getattr(run, "rows_processed", None),
        "rows_matched": getattr(run, "rows_matched", None),
        "rows_created": getattr(run, "rows_created", None),
        "rows_flagged": getattr(run, "rows_flagged", None),
        "rows_duplicates_prevented": getattr(run, "rows_duplicates_prevented", None),
        "duration_seconds": duration_seconds,
        "error_summary": getattr(run, "error_summary", None),
    }


def get_ops_dashboard_summary(db: Session) -> dict[str, int]:
    row = db.execute(
        text(
            """
            select
                (
                    select count(*)
                    from public.scrape_runs
                    where source_name = 'smartjobs'
                      and status = 'running'
                      and started_at >= now() - interval '2 hours'
                ) as active_runs,
                (
                    select count(*)
                    from public.scrape_runs
                    where source_name = 'smartjobs'
                      and status = 'failed'
                      and started_at >= now() - interval '7 days'
                ) as failed_runs_7d,
                (
                    select count(*)
                    from public.review_queue
                    where review_status in ('new', 'pending', 'open', 'watchlist')
                ) as pending_review_items,
                (
                    select count(*)
                    from public.scrape_runs
                    where source_name = 'smartjobs'
                      and status = 'running'
                      and started_at < now() - interval '2 hours'
                ) as stale_running_runs
            """
        )
    ).mappings().one()

    return {
        "active_runs": row["active_runs"],
        "failed_runs_7d": row["failed_runs_7d"],
        "pending_linkedin_reviews": row["pending_review_items"],
        "stale_running_runs": row["stale_running_runs"],
    }


def _scrape_run_row_to_dict(row: Any) -> dict[str, Any]:
    started_at = row["started_at"]
    finished_at = row["finished_at"]
    duration_seconds = None
    if started_at and finished_at:
        duration_seconds = int((finished_at - started_at).total_seconds())

    return {
        "id": row["id"],
        "source_name": row["source_name"],
        "started_at": started_at,
        "finished_at": finished_at,
        "status": row["status"],
        "jobs_seen": row["jobs_seen"],
        "jobs_matched": row["jobs_matched"],
        "review_items_created": row["review_items_created"],
        "duplicates_skipped": row["duplicates_skipped"],
        "duration_seconds": duration_seconds,
        "error_message": row["error_message"],
    }


def list_smartjobs_runs(db: Session, limit: int = 8):
    rows = db.execute(
        text(
            """
            select
                id, source_name, started_at, finished_at, status,
                jobs_seen, jobs_matched, review_items_created,
                duplicates_skipped, error_message
            from public.scrape_runs
            where source_name = 'smartjobs'
            order by started_at desc, id desc
            limit :limit
            """
        ),
        {"limit": limit},
    ).mappings().all()
    return [_scrape_run_row_to_dict(row) for row in rows]


def list_smartjobs_runs_for_day(db: Session, day: datetime.date):
    start_of_day = datetime.combine(day, datetime.min.time(), tzinfo=BRISBANE_TZ)
    end_of_day = start_of_day + timedelta(days=1)
    rows = db.execute(
        text(
            """
            select
                id, source_name, started_at, finished_at, status,
                jobs_seen, jobs_matched, review_items_created,
                duplicates_skipped, error_message
            from public.scrape_runs
            where source_name = 'smartjobs'
              and started_at >= :start_of_day
              and started_at < :end_of_day
            order by started_at desc, id desc
            limit 10
            """
        ),
        {
            "start_of_day": start_of_day.astimezone(timezone.utc),
            "end_of_day": end_of_day.astimezone(timezone.utc),
        },
    ).mappings().all()
    return [_scrape_run_row_to_dict(row) for row in rows]


def list_review_queue_runs(db: Session, limit: int = 8):
    runs = (
        db.query(models.WorkflowRun)
        .filter(models.WorkflowRun.run_type == "review_queue")
        .order_by(models.WorkflowRun.started_at.desc(), models.WorkflowRun.id.desc())
        .limit(limit)
        .all()
    )
    return [_workflow_run_to_dict(run) for run in runs]


def list_linkedin_import_runs_ui(db: Session, limit: int = 8):
    runs = (
        db.query(models.LinkedinImportRun)
        .order_by(models.LinkedinImportRun.uploaded_at.desc(), models.LinkedinImportRun.id.desc())
        .limit(limit)
        .all()
    )
    return [_linkedin_import_run_to_dict(run) for run in runs]


def list_ops_attention_items(db: Session):
    scrape_rows = db.execute(
        text(
            """
            select source_name, status
            from public.scrape_runs
            where source_name = 'smartjobs'
              and (
                (status = 'failed' and started_at >= now() - interval '7 days')
                or
                (status = 'running' and started_at < now() - interval '2 hours')
              )
            order by started_at desc
            limit 10
            """
        )
    ).mappings().all()

    attention = []
    for row in scrape_rows:
        attention.append(
            {
                "label": f"{row['source_name']} scrape · {row['status']}",
                "severity": "high" if row["status"] == "failed" else "medium",
            }
        )

    pending_review_items = db.execute(
        text(
            """
            select count(*)
            from public.review_queue
            where review_status in ('new', 'pending', 'open', 'watchlist')
            """
        )
    ).scalar_one()
    if pending_review_items:
        attention.append(
            {
                "label": f"{pending_review_items} review items awaiting action",
                "severity": "medium",
            }
        )

    linkedin_pending = (
        db.query(models.LinkedinConnectionStaging)
        .filter(models.LinkedinConnectionStaging.review_status == "pending")
        .count()
    )
    if linkedin_pending:
        attention.append(
            {
                "label": f"{linkedin_pending} LinkedIn rows pending review",
                "severity": "medium",
            }
        )

    return attention

def get_daily_bd_actions(db: Session, today: datetime.date, contact_limit: int = 25) -> dict[str, Any]:
    """Return a transparent, read-only daily BD action list."""
    due_tasks = db.execute(
        text(
            """
            select
                t.id as task_id,
                t.task_type,
                t.reason,
                t.priority,
                t.due_date,
                c.id as contact_id,
                coalesce(c.full_name, trim(concat_ws(' ', c.first_name, c.last_name))) as contact_name,
                o.id as organisation_id,
                o.name as organisation_name
            from public.tasks t
            left join public.contacts c on c.id = t.contact_id
            left join public.organisations o on o.id = coalesce(t.organisation_id, c.organisation_id)
            where coalesce(lower(t.status), 'open') not in ('completed', 'complete', 'cancelled', 'canceled')
              and t.due_date is not null
              and t.due_date <= :today
            order by
                case when t.due_date < :today then 0 else 1 end,
                case lower(coalesce(t.priority, ''))
                    when 'high' then 0 when 'medium' then 1 when 'low' then 2 else 3 end,
                t.due_date asc,
                t.id asc
            limit 50
            """
        ),
        {"today": today},
    ).mappings().all()

    due_contacts = db.execute(
        text(
            """
            with last_contact_activity as (
                select contact_id, max(activity_date::date) as last_activity_date
                from public.activities
                where contact_id is not null
                group by contact_id
            ),
            open_contact_tasks as (
                select distinct contact_id
                from public.tasks
                where contact_id is not null
                  and coalesce(lower(status), 'open') not in ('completed', 'complete', 'cancelled', 'canceled')
            )
            select
                c.id as contact_id,
                coalesce(c.full_name, trim(concat_ws(' ', c.first_name, c.last_name))) as contact_name,
                c.position_title,
                c.linkedin_profile_url,
                c.linkedin_connection_status,
                o.id as organisation_id,
                o.name as organisation_name,
                o.tier,
                lca.last_activity_date,
                case
                    when o.tier = 'Tier 1' then 30
                    when o.tier = 'Tier 2' then 60
                    else 90
                end as cadence_days,
                case
                    when lower(coalesce(c.linkedin_connection_status, '')) in ('not connected', 'not_connected', 'no')
                        then 'Send LinkedIn connection request'
                    when c.linkedin_profile_url is not null and trim(c.linkedin_profile_url) <> ''
                        then 'Send LinkedIn message or log an activity'
                    else 'Research contact channel and log an activity'
                end as recommended_action
            from public.contacts c
            join public.organisations o on o.id = c.organisation_id and o.is_archived = false
            left join last_contact_activity lca on lca.contact_id = c.id
            left join open_contact_tasks oct on oct.contact_id = c.id
            where oct.contact_id is null
              and (
                    lca.last_activity_date is null
                    or lca.last_activity_date <= :today - (
                        case
                            when o.tier = 'Tier 1' then 30
                            when o.tier = 'Tier 2' then 60
                            else 90
                        end
                    )
              )
            order by
                case o.tier when 'Tier 1' then 0 when 'Tier 2' then 1 when 'Tier 3' then 2 else 3 end,
                lca.last_activity_date asc nulls first,
                c.id asc
            limit :contact_limit
            """
        ),
        {"today": today, "contact_limit": contact_limit},
    ).mappings().all()

    due_contact_total = db.execute(
        text(
            """
            with last_contact_activity as (
                select contact_id, max(activity_date::date) as last_activity_date
                from public.activities
                where contact_id is not null
                group by contact_id
            ),
            open_contact_tasks as (
                select distinct contact_id
                from public.tasks
                where contact_id is not null
                  and coalesce(lower(status), 'open') not in ('completed', 'complete', 'cancelled', 'canceled')
            )
            select count(*)
            from public.contacts c
            join public.organisations o on o.id = c.organisation_id and o.is_archived = false
            left join last_contact_activity lca on lca.contact_id = c.id
            left join open_contact_tasks oct on oct.contact_id = c.id
            where oct.contact_id is null
              and (
                    lca.last_activity_date is null
                    or lca.last_activity_date <= :today - (
                        case when o.tier = 'Tier 1' then 30 when o.tier = 'Tier 2' then 60 else 90 end
                    )
              )
            """
        ),
        {"today": today},
    ).scalar_one()

    linkedin_opportunities = db.execute(
        text(
            """
            select
                c.id as contact_id,
                coalesce(c.full_name, trim(concat_ws(' ', c.first_name, c.last_name))) as contact_name,
                c.position_title,
                c.linkedin_profile_url,
                o.id as organisation_id,
                o.name as organisation_name,
                o.tier
            from public.contacts c
            join public.organisations o on o.id = c.organisation_id and o.is_archived = false
            where lower(coalesce(c.linkedin_connection_status, '')) in ('not connected', 'not_connected', 'no')
              and c.linkedin_profile_url is not null
              and trim(c.linkedin_profile_url) <> ''
            order by case o.tier when 'Tier 1' then 0 when 'Tier 2' then 1 else 2 end, c.id asc
            limit 25
            """
        )
    ).mappings().all()

    missing_linkedin_status = db.execute(
        text(
            """
            select
                c.id as contact_id,
                coalesce(c.full_name, trim(concat_ws(' ', c.first_name, c.last_name))) as contact_name,
                o.id as organisation_id,
                o.name as organisation_name,
                'Missing LinkedIn connection status' as reason
            from public.contacts c
            join public.organisations o on o.id = c.organisation_id and o.is_archived = false
            where c.linkedin_connection_status is null or trim(c.linkedin_connection_status) = ''
            order by c.id asc
            limit 25
            """
        )
    ).mappings().all()

    pending_linkedin_reviews = db.execute(
        text(
            """
            select count(*)
            from public.linkedin_connection_staging
            where review_status = 'pending'
            """
        )
    ).scalar_one()

    pending_review_queue = db.execute(
        text(
            """
            select count(*)
            from public.review_queue
            where review_status in ('new', 'pending', 'open', 'watchlist')
            """
        )
    ).scalar_one()

    return {
        "due_tasks": [dict(row) for row in due_tasks],
        "due_contacts": [dict(row) for row in due_contacts],
        "due_contact_total": due_contact_total,
        "linkedin_opportunities": [dict(row) for row in linkedin_opportunities],
        "missing_linkedin_status": [dict(row) for row in missing_linkedin_status],
        "pending_linkedin_reviews": pending_linkedin_reviews,
        "pending_review_queue": pending_review_queue,
    }
# -------------------------------------------------------------------
# Reports
# -------------------------------------------------------------------

def get_reports_activity_by_organisation(
    db: Session,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            select
                coalesce(o.name, 'Unassigned organisation') as organisation_name,
                count(a.id) as activity_count
            from public.activities a
            left join public.organisations o on o.id = a.organisation_id
            where (a.activity_date at time zone 'Australia/Brisbane')::date >= :period_start
              and (a.activity_date at time zone 'Australia/Brisbane')::date < :period_end
            group by coalesce(o.name, 'Unassigned organisation')
            order by activity_count desc, organisation_name asc
            """
        ),
        {"period_start": period_start, "period_end": period_end},
    ).mappings().all()
    return [dict(row) for row in rows]


def get_reports_activity_by_type(
    db: Session,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            select
                coalesce(nullif(trim(a.activity_type), ''), 'Unspecified') as activity_type,
                count(a.id) as activity_count
            from public.activities a
            where (a.activity_date at time zone 'Australia/Brisbane')::date >= :period_start
              and (a.activity_date at time zone 'Australia/Brisbane')::date < :period_end
            group by coalesce(nullif(trim(a.activity_type), ''), 'Unspecified')
            order by activity_count desc, activity_type asc
            """
        ),
        {"period_start": period_start, "period_end": period_end},
    ).mappings().all()
    return [dict(row) for row in rows]


def get_reports_activity_by_contact(
    db: Session,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            select
                coalesce(o.name, 'Unassigned organisation') as organisation_name,
                coalesce(
                    nullif(trim(c.full_name), ''),
                    nullif(trim(concat_ws(' ', c.first_name, c.last_name)), ''),
                    'Unassigned contact'
                ) as contact_name,
                count(a.id) as activity_count
            from public.activities a
            left join public.contacts c on c.id = a.contact_id
            left join public.organisations o on o.id = coalesce(a.organisation_id, c.organisation_id)
            where (a.activity_date at time zone 'Australia/Brisbane')::date >= :period_start
              and (a.activity_date at time zone 'Australia/Brisbane')::date < :period_end
            group by
                coalesce(o.name, 'Unassigned organisation'),
                coalesce(
                    nullif(trim(c.full_name), ''),
                    nullif(trim(concat_ws(' ', c.first_name, c.last_name)), ''),
                    'Unassigned contact'
                )
            order by organisation_name asc, activity_count desc, contact_name asc
            """
        ),
        {"period_start": period_start, "period_end": period_end},
    ).mappings().all()
    return [dict(row) for row in rows]


def get_reports_linkedin_connection_opportunities(
    db: Session,
    organisation_id: int | None = None,
    statuses: tuple[str, ...] = (
        "not_connected",
        "unknown",
    ),
) -> list[dict[str, Any]]:
    requested_statuses = {
        status.strip().lower()
        for status in statuses
        if status.strip()
    }

    include_not_connected = "not_connected" in requested_statuses
    include_unknown = "unknown" in requested_statuses
    include_pending = "pending" in requested_statuses

    if not (
        include_not_connected
        or include_unknown
        or include_pending
    ):
        return []

    rows = db.execute(
        text(
            """
            select
                c.id as contact_id,
                coalesce(
                    nullif(trim(c.full_name), ''),
                    nullif(trim(concat_ws(' ', c.first_name, c.last_name)), ''),
                    'Unnamed contact'
                ) as contact_name,
                c.position_title,
                c.department,
                c.email,
                c.linkedin_profile_url,
                c.linkedin_connection_status,
                c.linkedin_invitation_sent_at,
                c.source_type,
                c.created_at,
                o.id as organisation_id,
                o.name as organisation_name,
                count(t.id) filter (
                    where coalesce(lower(t.status), 'open')
                    not in ('completed', 'complete', 'cancelled', 'canceled')
                ) as open_task_count,
                case
                    when lower(trim(coalesce(c.linkedin_connection_status, '')))
                         in ('not connected', 'not_connected', 'no')
                        then 'not_connected'
                    when lower(trim(coalesce(c.linkedin_connection_status, '')))
                         in ('pending', 'pending invitation')
                        then 'pending'
                    else 'unknown'
                end as linkedin_status_group
            from public.contacts c
            join public.organisations o
              on o.id = c.organisation_id
             and o.is_archived = false
            left join public.tasks t on t.contact_id = c.id
            where (:organisation_id is null or c.organisation_id = :organisation_id)
              and (
                    (
                        :include_not_connected
                        and lower(trim(coalesce(c.linkedin_connection_status, '')))
                            in ('not connected', 'not_connected', 'no')
                    )
                    or
                    (
                        :include_pending
                        and lower(trim(coalesce(c.linkedin_connection_status, '')))
                            in ('pending', 'pending invitation')
                    )
                    or
                    (
                        :include_unknown
                        and lower(trim(coalesce(c.linkedin_connection_status, '')))
                            not in (
                                'connected',
                                'yes',
                                'not connected',
                                'not_connected',
                                'no',
                                'pending',
                                'pending invitation'
                            )
                    )
              )
            group by
                c.id,
                c.full_name,
                c.first_name,
                c.last_name,
                c.position_title,
                c.department,
                c.email,
                c.linkedin_profile_url,
                c.linkedin_connection_status,
                c.linkedin_invitation_sent_at,
                c.source_type,
                c.created_at,
                o.id,
                o.name
            order by
                case
                    when lower(trim(coalesce(c.linkedin_connection_status, '')))
                         in ('not connected', 'not_connected', 'no')
                        then 0
                    when lower(trim(coalesce(c.linkedin_connection_status, '')))
                         in ('pending', 'pending invitation')
                        then 1
                    else 2
                end,
                o.name asc,
                contact_name asc
            """
        ),
        {
            "organisation_id": organisation_id,
            "include_not_connected": include_not_connected,
            "include_unknown": include_unknown,
            "include_pending": include_pending,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def get_reports_linkedin_connections_by_organisation(
    db: Session,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            select
                o.name as organisation_name,
                count(c.id) as total_contacts,
                count(c.id) filter (
                    where lower(trim(coalesce(c.linkedin_connection_status, '')))
                    in ('connected', 'yes')
                ) as connected_count,
                count(c.id) filter (
                    where lower(trim(coalesce(c.linkedin_connection_status, '')))
                    in ('not connected', 'not_connected', 'no')
                ) as not_connected_count,
                count(c.id) filter (
                    where lower(trim(coalesce(c.linkedin_connection_status, '')))
                    not in ('connected', 'yes', 'not connected', 'not_connected', 'no')
                ) as unknown_count
            from public.organisations o
            join public.contacts c on c.organisation_id = o.id
            where o.is_archived = false
            group by o.id, o.name
            order by connected_count desc, total_contacts desc, o.name asc
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def get_reports_organisations_needing_attention(
    db: Session,
    as_at_date: date,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            with organisation_activity_dates as (
                select
                    coalesce(a.organisation_id, c.organisation_id) as organisation_id,
                    max((a.activity_date at time zone 'Australia/Brisbane')::date) as last_activity_date
                from public.activities a
                left join public.contacts c on c.id = a.contact_id
                where coalesce(a.organisation_id, c.organisation_id) is not null
                group by coalesce(a.organisation_id, c.organisation_id)
            ),
            organisation_last_touch as (
                select
                    o.id as organisation_id,
                    case
                        when o.last_contact_date is null then ad.last_activity_date
                        when ad.last_activity_date is null then o.last_contact_date
                        else greatest(o.last_contact_date, ad.last_activity_date)
                    end as last_touch_date,
                    ad.last_activity_date
                from public.organisations o
                left join organisation_activity_dates ad on ad.organisation_id = o.id
            )
            select
                o.id as organisation_id,
                o.name as organisation_name,
                o.tier,
                o.account_status,
                o.last_contact_date,
                olt.last_activity_date,
                olt.last_touch_date
            from public.organisations o
            join organisation_last_touch olt on olt.organisation_id = o.id
            where o.is_archived = false
              and (
                    olt.last_touch_date is null
                    or olt.last_touch_date <= :as_at_date - (
                        case
                            when o.tier = 'Tier 1' then 30
                            when o.tier = 'Tier 2' then 60
                            else 90
                        end
                    )
              )
            order by olt.last_touch_date asc nulls first, o.name asc
            """
        ),
        {"as_at_date": as_at_date},
    ).mappings().all()
    return [dict(row) for row in rows]
