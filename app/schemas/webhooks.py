from typing import Optional, Any
from pydantic import BaseModel

class ReviewQueueCreate(BaseModel):
    source_type: str
    review_type: str
    source_record_key: str
    source_payload: dict[str, Any]
    scraped_organisation: Optional[str] = None
    scraped_contact_name: Optional[str] = None
    scraped_contact_email: Optional[str] = None
    scraped_contact_phone: Optional[str] = None
    job_title: Optional[str] = None
    job_url: Optional[str] = None
    best_candidate_checked: Optional[str] = None
    best_score: Optional[float] = None