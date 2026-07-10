from datetime import datetime, UTC

from sqlalchemy import text


def start_scrape_run(db, source_name="smartjobs", notes=None):
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
                notes,
                created_at
            )
            values (
                :source_name,
                :started_at,
                'running',
                0,
                0,
                0,
                0,
                0,
                :notes,
                :created_at
            )
            returning id
        """),
        {
            "source_name": source_name,
            "started_at": datetime.now(UTC),
            "notes": notes,
            "created_at": datetime.now(UTC),
        },
    ).mappings().first()

    db.commit()
    return row["id"]


def flush_scrape_run_progress(
    db,
    run_id,
    jobs_seen,
    jobs_matched,
    review_items_created,
    duplicates_skipped,
    error_count,
):
    db.execute(
        text("""
            update public.scrape_runs
            set
                jobs_seen = :jobs_seen,
                jobs_matched = :jobs_matched,
                review_items_created = :review_items_created,
                duplicates_skipped = :duplicates_skipped,
                error_count = :error_count
            where id = :run_id
        """),
        {
            "run_id": run_id,
            "jobs_seen": jobs_seen,
            "jobs_matched": jobs_matched,
            "review_items_created": review_items_created,
            "duplicates_skipped": duplicates_skipped,
            "error_count": error_count,
        },
    )
    db.commit()


def record_scrape_run_error(db, run_id, error_message):
    db.execute(
        text("""
            update public.scrape_runs
            set
                error_count = coalesce(error_count, 0) + 1,
                error_message = :error_message
            where id = :run_id
        """),
        {
            "run_id": run_id,
            "error_message": str(error_message)[:2000],
        },
    )
    db.commit()


def finish_scrape_run_success(db, run_id, notes=None):
    db.execute(
        text("""
            update public.scrape_runs
            set
                status = 'success',
                finished_at = :finished_at,
                notes = coalesce(:notes, notes)
            where id = :run_id
        """),
        {
            "run_id": run_id,
            "finished_at": datetime.now(UTC),
            "notes": notes,
        },
    )
    db.commit()


def finish_scrape_run_partial(db, run_id, error_message=None, notes=None):
    db.execute(
        text("""
            update public.scrape_runs
            set
                status = 'partial',
                finished_at = :finished_at,
                error_message = coalesce(:error_message, error_message),
                notes = coalesce(:notes, notes)
            where id = :run_id
        """),
        {
            "run_id": run_id,
            "finished_at": datetime.now(UTC),
            "error_message": str(error_message)[:2000] if error_message else None,
            "notes": notes,
        },
    )
    db.commit()


def finish_scrape_run_failed(db, run_id, error_message=None, notes=None):
    db.execute(
        text("""
            update public.scrape_runs
            set
                status = 'failed',
                finished_at = :finished_at,
                error_message = coalesce(:error_message, error_message),
                notes = coalesce(:notes, notes)
            where id = :run_id
        """),
        {
            "run_id": run_id,
            "finished_at": datetime.now(UTC),
            "error_message": str(error_message)[:2000] if error_message else None,
            "notes": notes,
        },
    )
    db.commit()