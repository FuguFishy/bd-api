from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict

ReviewType = Literal[
    "unmatched_organisation",
    "unmatched_contact",
    "duplicate_contact",
    "duplicate_organisation",
]

ReviewStatus = Literal[
    "new",
    "resolved",
    "ignored",
    "watchlist",
]

ReviewResolveAction = Literal[
    "ignore",
    "watchlist",
    "match_existing_organisation",
    "create_organisation",
    "create_organisation_and_contact",
    "create_contact_for_existing_organisation",
]


class ReviewQueueCreate(BaseModel):
    source_type: str
    review_type: ReviewType
    source_record_key: str
    source_payload: dict[str, Any]

    scraped_organisation: Optional[str] = None
    scraped_contact_name: Optional[str] = None
    scraped_contact_email: Optional[str] = None
    scraped_contact_phone: Optional[str] = None
    job_title: Optional[str] = None
    job_url: Optional[str] = None

    best_candidate_checked: Optional[bool] = None
    best_score: Optional[float] = None


class ReviewQueueCreateResponse(BaseModel):
    created_new_review_item: bool
    ok: bool
    review_queue_id: int
    review_status: str


class ReviewQueueResolveRequest(BaseModel):
    action: ReviewResolveAction
    resolved_by: str
    review_notes: Optional[str] = None

    organisation_id: Optional[int] = None
    organisation_name: Optional[str] = None
    organisation_short_name: Optional[str] = None
    sector: Optional[str] = None
    tier: Optional[str] = None
    account_status: Optional[str] = None

    create_contact: bool = False
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_position_title: Optional[str] = None
    contact_department: Optional[str] = None


class ReviewQueueResolveResponse(BaseModel):
    ok: bool
    review_queue_id: int
    review_status: str
    review_action: str
    linked_organisation_id: Optional[int] = None
    linked_contact_id: Optional[int] = None


class ReviewQueueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    review_type: str
    review_status: str
    source_record_key: str
    source_payload: dict[str, Any]

    scraped_organisation: Optional[str] = None
    scraped_contact_name: Optional[str] = None
    scraped_contact_email: Optional[str] = None
    scraped_contact_phone: Optional[str] = None
    job_title: Optional[str] = None
    job_url: Optional[str] = None

    best_candidate_checked: Optional[bool] = None
    best_score: Optional[float] = None

    linked_organisation_id: Optional[int] = None
    linked_contact_id: Optional[int] = None

    review_action: Optional[str] = None
    review_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime