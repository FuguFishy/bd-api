from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func

from app.db.session import get_db
from app.models.review_queue import ReviewQueue
from app.schemas.review_queue import ReviewQueueCreate

router = APIRouter(prefix="/webhooks/n8n", tags=["n8n-webhooks"])


@router.post("/smartjobs-review-item")
def smartjobs_review_item(payload: ReviewQueueCreate, db: Session = Depends(get_db)):
    stmt = insert(ReviewQueue).values(
        source_type=payload.source_type,
        review_type=payload.review_type,
        source_record_key=payload.source_record_key,
        source_payload=payload.source_payload,
        scraped_organisation=payload.scraped_organisation,
        scraped_contact_name=payload.scraped_contact_name,
        scraped_contact_email=payload.scraped_contact_email,
        scraped_contact_phone=payload.scraped_contact_phone,
        job_title=payload.job_title,
        job_url=payload.job_url,
        best_candidate_checked=payload.best_candidate_checked,
        best_score=payload.best_score,
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=["source_type", "review_type", "source_record_key"],
        set_={
            "source_payload": payload.source_payload,
            "scraped_organisation": payload.scraped_organisation,
            "scraped_contact_name": payload.scraped_contact_name,
            "scraped_contact_email": payload.scraped_contact_email,
            "scraped_contact_phone": payload.scraped_contact_phone,
            "job_title": payload.job_title,
            "job_url": payload.job_url,
            "best_candidate_checked": payload.best_candidate_checked,
            "best_score": payload.best_score,
            "updated_at": func.now(),
        },
    ).returning(ReviewQueue.id, ReviewQueue.review_status)

    result = db.execute(stmt).first()
    db.commit()

    return {
        "ok": True,
        "review_queue_id": result.id,
        "review_status": result.review_status,
    }