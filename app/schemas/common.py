from pydantic import BaseModel


class DropdownItem(BaseModel):
    id: int
    label: str


class WeeklyReportOut(BaseModel):
    meeting_count: int
    target: int | None = None
    daily_breakdown: dict | None = None
    gaps: list[str] | None = None