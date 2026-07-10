from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/scrape-runs", tags=["scrape-runs"])


@router.get("")
def list_scrape_runs(
    source_name: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
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

    return [dict(row) for row in rows]


@router.get("/{run_id}")
def get_scrape_run(
    run_id: int,
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
    where id = :run_id
    """
    row = db.execute(
        text(sql),
        {"run_id": run_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Scrape run not found")

    return dict(row)