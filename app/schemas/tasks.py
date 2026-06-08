from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TaskBase(BaseModel):
    contact_id: Optional[int] = None
    organisation_id: Optional[int] = None
    project_id: Optional[int] = None
    activity_id: Optional[int] = None
    task_type: str
    reason: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = "open"
    due_date: Optional[date] = None
    owner: Optional[str] = None
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)
    id: int