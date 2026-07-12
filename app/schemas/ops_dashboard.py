from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ops_dashboard import (
    OpsDashboardResponse,
    OpsDashboardReviewAction,
    OpsDashboardReviewItem,
    OpsDashboardScrapeRun,
    OpsDashboardSummary,
    OpsDashboardWorkflowRun,
)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("select 1"))
        return {
            "status": "ok",
            "service": "bd-api",
            "database": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "service": "bd-api",
                "database": "unreachable",
                "message": str(exc),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )


@router.get("/dashboard", response_model=OpsDashboardResponse)
def get_ops_dashboard(db: Session = Depends(get_db)):
    try:
        summary_row = db.execute(
            text(
                """
                select
                    (
                        select count(*)
                        from public.review_queue
                        where review_status in ('new', 'pending', 'open', 'watchlist')
                    ) as open_review_queue_count,
                    (
                        select count(*)
                        from public.review_queue
                        where review_status = 'resolved'
                    ) as resolved_review_queue_count,
                    (
                        select count(*)
                        from public.workflowruns
                        where status = 'failed'
                          and startedat >= now() - interval '7 days'
                    ) as failed_workflow_count_7d,
                    (
                        select count(*)
                        from public.scrape_runs
                        where status = 'failed'
                          and started_at >= now() - interval '7 days'
                    ) as failed_scrape_count_7d
                """
            )
        ).mappings().first()

        scrape_rows = db.execute(
            text(
                """
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
                    error_message
                from public.scrape_runs
                order by started_at desc
                limit 10
                """
            )
        ).mappings().all()

        workflow_rows = db.execute(
            text(
                """
                select
                    id,
                    workflowname,
                    runtype,
                    startedat,
                    finishedat,
                    status,
                    recordsprocessed,
                    recordsflagged,
                    errorsummary
                from public.workflowruns
                where status = 'failed'
                order by startedat desc
                limit 10
                """
            )
        ).mappings().all()

        review_rows = db.execute(
            text(
                """
                select
                    id,
                    source_type,
                    review_type,
                    review_status,
                    source_record_key,
                    scraped_organisation,
                    scraped_contact_name,
                    job_title,
                    best_score,
                    created_at,
                    resolved_by,
                    resolved_at
                from public.review_queue
                where review_status in ('new', 'pending', 'open', 'watchlist')
                order by created_at desc
                limit 20
                """
            )
        ).mappings().all()

        action_rows = db.execute(
            text(
                """
                select
                    id,
                    review_queue_id,
                    action_type,
                    action_notes,
                    action_by,
                    created_at
                from public.review_queue_actions
                order by created_at desc
                limit 20
                """
            )
        ).mappings().all()

        return OpsDashboardResponse(
            summary=OpsDashboardSummary(**dict(summary_row)),
            latest_scrape_runs=[
                OpsDashboardScrapeRun(**dict(row)) for row in scrape_rows
            ],
            failed_workflow_runs=[
                OpsDashboardWorkflowRun(**dict(row)) for row in workflow_rows
            ],
            open_review_items=[
                OpsDashboardReviewItem(**dict(row)) for row in review_rows
            ],
            recent_review_actions=[
                OpsDashboardReviewAction(**dict(row)) for row in action_rows
            ],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": str(exc),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )