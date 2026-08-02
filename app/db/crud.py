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
    include_archived: bool = False,
):
    query = db.query(models.Organisation)

    if not include_archived:
        query = query.filter(models.Organisation.is_archived.is_(False))

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
    include_archived: bool = False,
):
    return list_organisations(
        db=db,
        q=q,
        sector=sector,
        tier=tier,
        account_status=account_status,
        include_archived=include_archived,
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
        .filter(
            models.Contact.organisation_id == organisation_id,
            models.Contact.is_archived.is_(False),
        )
        .order_by(models.Contact.last_name.asc(), models.Contact.first_name.asc())
        .all()
    )

    projects = (
        db.query(models.Project)
        .filter(
            models.Project.organisation_id == organisation_id,
            models.Project.is_archived.is_(False),
        )
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
    include_archived: bool = False,
):
    query = db.query(models.Contact)

    if not include_archived:
        query = query.filter(models.Contact.is_archived.is_(False))

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
        .filter(
            models.Project.organisation_id == contact.organisation_id,
            models.Project.is_archived.is_(False),
        )
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
    include_archived: bool = False,
):
    query = db.query(models.Project)

    if not include_archived:
        query = query.filter(models.Project.is_archived.is_(False))

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