from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OpsDashboardSummary(BaseModel):
    open_review_queue_count: int
    resolved_review_queue_count: int
    failed_workflow_count_7d: int
    failed_scrape_count_7d: int


class OpsDashboardScrapeRun(BaseModel):
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


class OpsDashboardWorkflowRun(BaseModel):
    id: int
    workflowname: str
    runtype: str
    startedat: datetime
    finishedat: Optional[datetime] = None
    status: str
    recordsprocessed: int
    recordsflagged: int
    errorsummary: Optional[str] = None


class OpsDashboardReviewItem(BaseModel):
    id: int
    source_type: str
    review_type: str
    review_status: str
    source_record_key: str
    scraped_organisation: Optional[str] = None
    scraped_contact_name: Optional[str] = None
    job_title: Optional[str] = None
    best_score: Optional[float] = None
    created_at: datetime
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


class OpsDashboardReviewAction(BaseModel):
    id: int
    review_queue_id: int
    action_type: str
    action_notes: Optional[str] = None
    action_by: Optional[str] = None
    created_at: datetime


class OpsDashboardResponse(BaseModel):
    summary: OpsDashboardSummary
    latest_scrape_runs: list[OpsDashboardScrapeRun]
    failed_workflow_runs: list[OpsDashboardWorkflowRun]
    open_review_items: list[OpsDashboardReviewItem]
    recent_review_actions: list[OpsDashboardReviewAction]