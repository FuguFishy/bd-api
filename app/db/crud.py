from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.activities import ActivityCreate
from app.schemas.contacts import ContactCreate
from app.schemas.organisations import OrganisationCreate
from app.schemas.projects import ProjectCreate
from app.schemas.tasks import TaskCreate


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
    contact_ids = list({activity.contact_id for activity in activities if getattr(activity, "contact_id", None)})
    project_ids = list({activity.project_id for activity in activities if getattr(activity, "project_id", None)})

    contact_lookup: dict[int, str] = {}
    if contact_ids:
        contact_rows = (
            db.query(models.Contact)
            .filter(models.Contact.id.in_(contact_ids))
            .all()
        )
        contact_lookup = {contact.id: _contact_display_name(contact) for contact in contact_rows}

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

    return query.order_by(models.Contact.full_name.asc()).all()


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

    return query.order_by(models.Activity.activity_date.desc()).all()


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

def get_ops_dashboard_summary(db: Session) -> dict[str, int]:
    active_runs = (
        db.query(models.WorkflowRun)
        .filter(models.WorkflowRun.status == "running")
        .count()
    )

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    failed_runs_7d = (
        db.query(models.WorkflowRun)
        .filter(
            models.WorkflowRun.status == "failed",
            models.WorkflowRun.started_at >= seven_days_ago,
        )
        .count()
    )

    pending_linkedin_reviews = (
        db.query(models.LinkedinConnectionStaging)
        .filter(models.LinkedinConnectionStaging.review_status == "pending")
        .count()
    )

    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    stale_running_runs = (
        db.query(models.WorkflowRun)
        .filter(
            models.WorkflowRun.status == "running",
            models.WorkflowRun.started_at < two_hours_ago,
        )
        .count()
    )

    return {
        "active_runs": active_runs,
        "failed_runs_7d": failed_runs_7d,
        "pending_linkedin_reviews": pending_linkedin_reviews,
        "stale_running_runs": stale_running_runs,
    }


def list_recent_workflow_runs(db: Session, limit: int = 20):
    runs = (
        db.query(models.WorkflowRun)
        .order_by(models.WorkflowRun.started_at.desc(), models.WorkflowRun.id.desc())
        .limit(limit)
        .all()
    )

    result = []
    for run in runs:
        duration_seconds = None
        if getattr(run, "started_at", None) and getattr(run, "finished_at", None):
            duration_seconds = int((run.finished_at - run.started_at).total_seconds())

        result.append(
            {
                "source": "workflow",
                "workflow_name": run.workflow_name,
                "status": run.status,
                "started_at": run.started_at,
                "duration_seconds": duration_seconds,
                "error_summary": run.error_summary,
            }
        )
    return result


def list_ops_attention_items(db: Session):
    rows = (
        db.query(models.WorkflowRun)
        .filter(models.WorkflowRun.status != "completed")
        .order_by(models.WorkflowRun.started_at.desc())
        .limit(10)
        .all()
    )

    attention = []
    for run in rows:
        severity = "medium"
        if run.status == "failed":
            severity = "high"
        elif run.status == "running":
            severity = "medium"

        attention.append(
            {
                "label": f"{run.workflow_name} · {run.status}",
                "severity": severity,
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