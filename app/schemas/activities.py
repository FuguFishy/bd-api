from datetime import datetime
from pydantic import BaseModel, ConfigDict

class ActivityCreate(BaseModel):
    contact_id: int | None = None
    organisation_id: int | None = None
    project_id: int | None = None
    activity_type: str
    activity_date: datetime
    outcome: str | None = None
    notes: str | None = None
    logged_by: str | None = None

class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int | None = None
    organisation_id: int | None = None
    project_id: int | None = None
    activity_type: str
    activity_date: datetime
    outcome: str | None = None
    notes: str | None = None
    logged_by: str | None = None