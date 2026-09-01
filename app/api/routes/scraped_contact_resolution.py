from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.scraped_contact_resolution import resolve_scraped_contact


router = APIRouter(
    prefix="/scraped-contact-resolution",
    tags=["scraped-contact-resolution"],
)


class ScrapedContactResolutionRequest(BaseModel):
    source_type: Literal["aps_jobs", "smartjobs"]
    source_record_key: str | None = None
    scraped_organisation: str | None = None
    scraped_contact_name: str | None = None
    scraped_contact_email: str | None = None
    linkedin_profile_url: str | None = None
    job_title: str | None = None
    job_url: str | None = None
    source_payload: dict = Field(default_factory=dict)


@router.post("/dry-run")
def dry_run_scraped_contact_resolution(
    payload: ScrapedContactResolutionRequest,
    db: Session = Depends(get_db),
):
    result = resolve_scraped_contact(
        db,
        source_type=payload.source_type,
        source_record_key=payload.source_record_key,
        scraped_organisation=payload.scraped_organisation,
        scraped_contact_name=payload.scraped_contact_name,
        scraped_contact_email=payload.scraped_contact_email,
        linkedin_profile_url=payload.linkedin_profile_url,
    )

    return {
        "mode": "dry_run",
        "source_type": payload.source_type,
        "source_record_key": payload.source_record_key,
        **result.to_dict(),
    }
