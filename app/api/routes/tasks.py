from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.crud import create_task, list_tasks
from app.db.session import get_db
from app.schemas.tasks import TaskCreate, TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead)
def create_task_route(payload: TaskCreate, db: Session = Depends(get_db)):
    return create_task(db, payload)


@router.get("", response_model=list[TaskRead])
def read_tasks(db: Session = Depends(get_db)):
    return list_tasks(db)