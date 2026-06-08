from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.crud import create_project, list_projects
from app.db.session import get_db
from app.schemas.projects import ProjectCreate, ProjectRead
from app.schemas.common import DropdownItem

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project_route(payload: ProjectCreate, db: Session = Depends(get_db)):
    return create_project(db, payload)


@router.get("", response_model=list[DropdownItem])
def read_projects(db: Session = Depends(get_db)):
    rows = list_projects(db)
    return [DropdownItem(id=p.id, label=p.name) for p in rows]