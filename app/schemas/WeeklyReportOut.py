from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.reports import WeeklyReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/weekly", response_model=WeeklyReportOut)
def weekly_report(db: Session = Depends(get_db)):
    return {
        "meeting_count": 0,
        "target": 0,
        "daily_breakdown": {},
        "gaps": [],
    }