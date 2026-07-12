from datetime import datetime, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.scrape_runs import (
    ScrapeRunFinishRequest,
    ScrapeRunOut,
    ScrapeRunResponse,
    ScrapeRunStartRequest,
)

router = APIRouter(prefix="/scrape-runs", tags=["scrape-runs"])


@router.get("", response_model=list[ScrapeRunOut])
def list_scrape_runs(
    source_name: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    sql = """
    select
        id,
        source_name,
        started_at,
        finished_at,
        status,
        jobs_seen,
        jobs_matched,
        review_items_created,
        duplicates_skipped,
        error_count,
        error_message,
        notes,
        created_at
    from public.scrape_runs
    where (:source_name is null or source_name = :source_name)
    order by started_at desc
    limit :limit
    """
    rows = db.execute(
        text(sql),
        {"source_name": source_name, "limit": limit},
    ).mappings().all()
    return [ScrapeRunOut(**dict(row)) for row in rows]


@router.post("/start", response_model=ScrapeRunResponse)
def start_scrape_run(
    payload: ScrapeRunStartRequest,
    db: Session = Depends(get_db),
):
    row = db.execute(
        text("""
        insert into public.scrape_runs (
            source_name,
            started_at,
            status,
            jobs_seen,
            jobs_matched,
            review_items_created,
            duplicates_skipped,
            error_count,
            error_message,
            notes,
            created_at
        )
        values (
            :source_name,
            :started_at,
            :status,
            0,
            0,
            0,
            0,
            0,
            null,
            :notes,
            :created_at
        )
        returning id, source_name, status
        """),
        {
            "source_name": payload.source_name,
            "started_at": datetime.now(UTC),
            "status": payload.status,
            "notes": payload.notes,
            "created_at": datetime.now(UTC),
        },
    ).mappings().first()

    db.commit()

    return ScrapeRunResponse(
        ok=True,
        scrape_run_id=row["id"],
        source_name=row["source_name"],
        status=row["status"],
    )


@router.post("/{scrape_run_id}/finish", response_model=ScrapeRunResponse)
def finish_scrape_run(
    scrape_run_id: int,
    payload: ScrapeRunFinishRequest,
    db: Session = Depends(get_db),
):
    existing = db.execute(
        text("""
        select id, source_name
        from public.scrape_runs
        where id = :scrape_run_id
        limit 1
        """),
        {"scrape_run_id": scrape_run_id},
    ).mappings().first()

    if not existing:
        raise HTTPException(status_code=404, detail="Scrape run not found")

    row = db.execute(
        text("""
        update public.scrape_runs
        set
            finished_at = :finished_at,
            status = :status,
            jobs_seen = :jobs_seen,
            jobs_matched = :jobs_matched,
            review_items_created = :review_items_created,
            duplicates_skipped = :duplicates_skipped,
            error_count = :error_count,
            error_message = :error_message,
            notes = :notes
        where id = :scrape_run_id
        returning id, source_name, status
        """),
        {
            "scrape_run_id": scrape_run_id,
            "finished_at": datetime.now(UTC),
            "status": payload.status,
            "jobs_seen": payload.jobs_seen,
            "jobs_matched": payload.jobs_matched,
            "review_items_created": payload.review_items_created,
            "duplicates_skipped": payload.duplicates_skipped,
            "error_count": payload.error_count,
            "error_message": payload.error_message,
            "notes": payload.notes,
        },
    ).mappings().first()

    db.commit()

    return ScrapeRunResponse(
        ok=True,
        scrape_run_id=row["id"],
        source_name=row["source_name"],
        status=row["status"],
    )