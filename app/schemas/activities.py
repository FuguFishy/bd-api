from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ActivityCreate(BaseModel):
    contact_name: str | None = None
    organisation_name: str | None = None
    project_name: str | None = None
    activity_type: str
    activity_date: datetime
    outcome: str | None = None
    notes: str | None = None


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_name: str | None = None
    organisation_name: str | None = None
    project_name: str | None = None
    activity_type: str
    activity_date: datetime
    outcome: str | None = None
    notes: str | None = None