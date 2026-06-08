from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.organisations import OrganisationCreate
from app.schemas.contacts import ContactCreate
from app.schemas.projects import ProjectCreate
from app.schemas.activities import ActivityCreate
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


def create_organisation(db: Session, payload: OrganisationCreate):
    obj = models.Organisation(**payload.model_dump())
    db.add(obj)
    _commit_or_raise(db, {"organisations_name_key": "Organisation already exists"}, "Unable to create organisation due to invalid data")
    db.refresh(obj)
    return obj


def list_organisations(db: Session):
    return db.query(models.Organisation).order_by(models.Organisation.name).all()


def create_contact(db: Session, payload: ContactCreate):
    obj = models.Contact(**payload.model_dump())
    db.add(obj)
    _commit_or_raise(db, {"contacts_email_key": "Contact email already exists"}, "Unable to create contact due to invalid data")
    db.refresh(obj)
    return obj


def list_contacts(db: Session):
    return db.query(models.Contact).order_by(models.Contact.last_name, models.Contact.first_name).all()


def create_project(db: Session, payload: ProjectCreate):
    obj = models.Project(**payload.model_dump())
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


def create_activity(db: Session, payload: ActivityCreate):
    obj = models.Activity(**payload.model_dump())
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create activity due to invalid data")
    db.refresh(obj)
    return obj


def list_activities(db: Session):
    return db.query(models.Activity).order_by(models.Activity.activity_date.desc()).all()


def create_task(db: Session, payload: TaskCreate):
    obj = models.Task(**payload.model_dump())
    db.add(obj)
    _commit_or_raise(db, {}, "Unable to create task due to invalid data")
    db.refresh(obj)
    return obj


def list_tasks(db: Session):
    return db.query(models.Task).order_by(models.Task.id.desc()).all()