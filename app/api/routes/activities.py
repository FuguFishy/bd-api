from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.crud import create_activity, list_activities
from app.db.session import get_db
from app.schemas.activities import ActivityCreate, ActivityRead

router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("", response_model=ActivityRead)
def create_activity_route(payload: ActivityCreate, db: Session = Depends(get_db)):
    return create_activity(db, payload)


@router.get("", response_model=list[ActivityRead])
def read_activities(db: Session = Depends(get_db)):
    return list_activities(db)