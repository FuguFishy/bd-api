from __future__ import annotations

from datetime import datetime, timezone
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


def _commit_or_raise(db: Session, duplicate_map: dict[str, str], default_message: str) -> None:
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
    full_name_field = (getattr(contact, "full_name", None) or "").strip()
    if full_name_field:
        return full_name_field

    first_name = (getattr(contact, "first_name", None) or "").strip()
    last_name = (getattr(contact, "last_name", None) or "").strip()
    combined = f"{first_name} {last_name}".strip()
    if combined:
        return combined

    return f"Contact {contact.id}"


def _enrich_contacts_with_organisation_names(db: Session, contacts: list[Any]) -> list[Any]:
    organisation_ids = list(
        {contact.organisation_id for contact in contacts if getattr(contact, "organisation_id", None)}
    )
    if not organisation_ids:
        return contacts

    organisation_rows = (
        db.query(models.Organisation)
        .filter(models.Organisation.id.in_(organisation_ids))
        .all()
    )
    organisation_lookup = {organisation.id: organisation.name for organisation in organisation_rows}

    for contact in contacts:
        contact.organisation_name = organisation_lookup.get(contact.organisation_id)

    return contacts


def _enrich_projects_with_organisation_names(db: Session, projects: list[Any]) -> list[Any]:
    organisation_ids = list(
        {project.organisation_id for project in projects if getattr(project, "organisation_id", None)}
    )
    if not organisation_ids:
        return projects

    organisation_rows = (
        db.query(models.Organisation)
        .filter(models.Organisation.id.in_(organisation_ids))
        .all()
    )
    organisation_lookup = {organisation.id: organisation.name for organisation in organisation_rows}

    for project in projects:
        project.organisation_name = organisation_lookup.get(project.organisation_id)

    return projects


def _enrich_activities_with_labels(db: Session, activities: list[Any]) -> list[Any]:
    organisation_ids = list(
        {activity.organisation_id for activity in activities if getattr(activity, "organisation_id", None)}
    )
    contact_ids = list(
        {activity.contact_id for activity in activities if getattr(activity, "contact_id", None)}
    )
    project_ids = list(
        {activity.project_id for activity in activities if getattr(activity, "project_id", None)}
    )

    organisation_lookup: dict[int, str] = {}
    if organisation_ids:
        organisation_rows = (
            db.query(models.Organisation)
            .filter(models.Organisation.id.in_(organisation_ids))
            .all()
        )
        organisation_lookup = {organisation.id: organisation.name for organisation in organisation_rows}

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
        activity.organisation_name = organisation_lookup.get(activity.organisation_id)
        activity.contact_label = contact_lookup.get(activity.contact_id)
        activity.project_label = project_lookup.get(activity.project_id)

    return activities


def _enrich_tasks_with_labels(db: Session, tasks: list[Any]) -> list[Any]:
    organisation_ids = list(
        {task.organisation_id for task in tasks if getattr(task, "organisation_id", None)}
    )
    contact_ids = list(
        {task.contact_id for task in tasks if getattr(task, "contact_id", None)}
    )
    project_ids = list(
        {task.project_id for task in tasks if getattr(task, "project_id", None)}
    )

    organisation_lookup: dict[int, str] = {}
    if organisation_ids:
        organisation_rows = (
            db.query(models.Organisation)
            .filter(models.Organisation.id.in_(organisation_ids))
            .all()
        )
        organisation_lookup = {organisation.id: organisation.name for organisation in organisation_rows}

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

    for task in tasks:
        task.organisation_name = organisation_lookup.get(task.organisation_id)
        task.contact_label = contact_lookup.get(task.contact_id)
        task.project_label = project_lookup.get(task.project_id)

    return tasks


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
    contacts = _enrich_contacts_with_organisation_names(db, contacts)

    projects = (
        db.query(models.Project)
        .filter(models.Project.organisation_id == organisation_id)
        .order_by(models.Project.name.asc())
        .all()
    )
    projects = _enrich_projects_with_organisation_names(db, projects)

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
    tasks = _enrich_tasks_with_labels(db, tasks)

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
    return _enrich_contacts_with_organisation_names(db, contacts)


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

    if getattr(contact, "organisation_id", None):
        organisation = get_organisation(db, contact.organisation_id)
        contact.organisation_name = organisation.name if organisation else None
    else:
        contact.organisation_name = None

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
    tasks = _enrich_tasks_with_labels(db, tasks)

    projects = (
        db.query(models.Project)
        .filter(models.Project.organisation_id == contact.organisation_id)
        .order_by(models.Project.name.asc())
        .all()
        if getattr(contact, "organisation_id", None)
        else []
    )
    projects = _enrich_projects_with_organisation_names(db, projects)

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

    projects = query.order_by(models.Project.name.asc()).all()
    return _enrich_projects_with_organisation_names(db, projects)


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
    tasks = _enrich_tasks_with_labels(db, tasks)

    organisation = None
    if getattr(project, "organisation_id", None):
        organisation = get_organisation(db, project.organisation_id)

    project.organisation_name = organisation.name if organisation else None

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

    tasks = query.order_by(models.Task.due_date.asc().nullslast(), models.Task.id.desc()).all()
    return _enrich_tasks_with_labels(db, tasks)


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
    obj = models.LinkedInImportRun(**_payload_dict(payload))
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create LinkedIn import run")
    db.refresh(obj)
    return obj


def list_linkedin_import_runs(
    db: Session,
    status: str | None = None,
):
    query = db.query(models.LinkedInImportRun)

    if status:
        query = query.filter(models.LinkedInImportRun.status == status)

    return query.order_by(models.LinkedInImportRun.uploaded_at.desc(), models.LinkedInImportRun.id.desc()).all()


def get_linkedin_import_run(db: Session, import_run_id: int):
    return (
        db.query(models.LinkedInImportRun)
        .filter(models.LinkedInImportRun.id == import_run_id)
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
    obj = models.LinkedInConnectionStaging(**_payload_dict(payload))
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
    objects = [models.LinkedInConnectionStaging(**row) for row in rows]
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
    query = db.query(models.LinkedInConnectionStaging)

    if import_run_id is not None:
        query = query.filter(models.LinkedInConnectionStaging.import_run_id == import_run_id)
    if match_status:
        query = query.filter(models.LinkedInConnectionStaging.match_status == match_status)
    if review_status:
        query = query.filter(models.LinkedInConnectionStaging.review_status == review_status)

    return query.order_by(models.LinkedInConnectionStaging.id.asc()).all()


def get_linkedin_connection_staging_row(db: Session, staging_row_id: int):
    return (
        db.query(models.LinkedInConnectionStaging)
        .filter(models.LinkedInConnectionStaging.id == staging_row_id)
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
# Ops / dashboard helpers
# -------------------------------------------------------------------

def get_ops_dashboard_summary(db: Session) -> dict[str, int]:
    return {
        "pending_linkedin_reviews": db.query(models.LinkedInConnectionStaging)
        .filter(models.LinkedInConnectionStaging.review_status == "pending")
        .count(),
        "open_tasks": db.query(models.Task)
        .filter(models.Task.completed_at.is_(None))
        .count(),
        "import_runs": db.query(models.LinkedInImportRun).count(),
        "organisations": db.query(models.Organisation).count(),
    }


def list_recent_workflow_runs(db: Session, limit: int = 20):
    return (
        db.query(models.LinkedInImportRun)
        .order_by(models.LinkedInImportRun.uploaded_at.desc(), models.LinkedInImportRun.id.desc())
        .limit(limit)
        .all()
    )


def list_ops_attention_items(db: Session) -> list[dict[str, Any]]:
    pending_reviews = (
        db.query(models.LinkedInConnectionStaging)
        .filter(models.LinkedInConnectionStaging.review_status == "pending")
        .count()
    )
    overdue_tasks = (
        db.query(models.Task)
        .filter(
            models.Task.completed_at.is_(None),
            models.Task.due_date.isnot(None),
            models.Task.due_date < datetime.now(timezone.utc),
        )
        .count()
    )

    items: list[dict[str, Any]] = []

    if pending_reviews:
        items.append(
            {
                "label": "Pending LinkedIn reviews",
                "count": pending_reviews,
                "href": "/ui/linkedin/review",
            }
        )

    if overdue_tasks:
        items.append(
            {
                "label": "Overdue tasks",
                "count": overdue_tasks,
                "href": "/ui/tasks",
            }
        )

    return items


def list_pending_linkedin_reviews(db: Session):
    return (
        db.query(models.LinkedInConnectionStaging)
        .filter(models.LinkedInConnectionStaging.review_status == "pending")
        .order_by(models.LinkedInConnectionStaging.id.asc())
        .all()
    )