from pydantic import BaseModel


class WeeklyReportOut(BaseModel):
    meeting_count: int
    target: int | None = None
    daily_breakdown: dict | None = None
    gaps: list[str] | None = None