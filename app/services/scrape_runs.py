from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ScrapeRunStartRequest(BaseModel):
    source_name: str
    status: str = "running"
    notes: Optional[str] = None


class ScrapeRunFinishRequest(BaseModel):
    status: str
    jobs_seen: int = 0
    jobs_matched: int = 0
    review_items_created: int = 0
    duplicates_skipped: int = 0
    error_count: int = 0
    error_message: Optional[str] = None
    notes: Optional[str] = None


class ScrapeRunResponse(BaseModel):
    ok: bool
    scrape_run_id: int
    source_name: str
    status: str


class ScrapeRunOut(BaseModel):
    id: int
    source_name: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: str
    jobs_seen: int
    jobs_matched: int
    review_items_created: int
    duplicates_skipped: int
    error_count: int
    error_message: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime