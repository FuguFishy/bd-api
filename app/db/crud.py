from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.organisations import OrganisationCreate
from app.schemas.contacts import ContactCreate
from app.schemas.projects import ProjectCreate
from app.schemas.activities import ActivityCreate, ActivityRead
from app.schemas.tasks import TaskCreate

def _commit_or_raise(db: Session, duplicate_map: dict[str, str], default_message: str):
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


def _resolve_organisation(db: Session, organisation_id: int | None, organisation_name: str | None):
    if organisation_id is not None:
        org = db.query(models.Organisation).filter(models.Organisation.id == organisation_id).first()
        if not org:
            raise HTTPException(status_code=400, detail="Organisation ID does not exist")
        return org

    if organisation_name:
        org = (
            db.query(models.Organisation)
            .filter(models.Organisation.name == organisation_name.strip())
            .first()
        )
        if not org:
            raise HTTPException(status_code=400, detail="Organisation name does not exist")
        return org

    raise HTTPException(status_code=400, detail="Organisation is required")


def create_organisation(db: Session, payload: OrganisationCreate):
    obj = models.Organisation(**payload.model_dump())
    db.add(obj)
    _commit_or_raise(
        db,
        {"organisations_name_key": "Organisation already exists"},
        "Unable to create organisation due to invalid data",
    )
    db.refresh(obj)
    return obj


def list_organisations(db: Session):
    return db.query(models.Organisation).order_by(models.Organisation.name).all()


def create_contact(db: Session, payload: ContactCreate):
    org = _resolve_organisation(db, payload.organisation_id, payload.organisation_name)

    first_name = (payload.first_name or "").strip()
    last_name = (payload.last_name or "").strip()
    full_name = f"{first_name} {last_name}".strip()

    obj = models.Contact(
        organisation_id=org.id,
        organisation_name=org.name,
        first_name=first_name,
        last_name=last_name,
        full_name=full_name,
        email=payload.email,
    )

    db.add(obj)
    _commit_or_raise(
        db,
        {"contacts_email_key": "Contact email already exists"},
        "Unable to create contact due to invalid data",
    )
    db.refresh(obj)
    return obj

from datetime import datetime

def list_contacts(db: Session):
    return db.query(models.Contact).order_by(models.Contact.last_name, models.Contact.first_name).all()


def create_project(db: Session, payload: ProjectCreate):
    org = _resolve_organisation(db, payload.organisation_id, payload.organisation_name)

    obj = models.Project(
        organisation_id=org.id,
        organisation_name=org.name,
        name=payload.name.strip(),
        status=payload.status,
        project_type=payload.project_type,
    )

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


def list_projects(db: Session):
    return db.query(models.Project).order_by(models.Project.name).all()


def create_activity(db: Session, payload: ActivityCreate) -> ActivityRead:
    obj = models.Activity(
        contact_id=None,
        organisation_id=None,
        project_id=None,
        activity_type=payload.activity_type,
        activity_date=payload.activity_date,
        outcome=payload.outcome,
        notes=payload.notes,
        logged_by="manual",
        created_at=datetime.utcnow(),
    )

    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create activity due to invalid data")
    db.refresh(obj)

    return ActivityRead(
        id=obj.id,
        contact_name=payload.contact_name,
        organisation_name=payload.organisation_name,
        project_name=payload.project_name,
        activity_type=obj.activity_type,
        activity_date=obj.activity_date,
        outcome=obj.outcome,
        notes=obj.notes,
    )

def list_activities(db: Session):
    rows = db.query(models.Activity).order_by(models.Activity.activity_date.desc()).all()

    return [
        ActivityRead(
            id=row.id,
            contact_name=None,
            organisation_name=None,
            project_name=None,
            activity_type=row.activity_type,
            activity_date=row.activity_date,
            outcome=row.outcome,
            notes=row.notes,
        )
        for row in rows
    ]

def create_task(db: Session, payload: TaskCreate):
    obj = models.Task(**payload.model_dump())
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create task due to invalid data")
    db.refresh(obj)
    return obj


def list_tasks(db: Session):
    return db.query(models.Task).order_by(models.Task.id.desc()).all()
