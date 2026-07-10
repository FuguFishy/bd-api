from app.db.session import SessionLocal
from app.services.scrape_run_monitor import (
    start_scrape_run,
    flush_scrape_run_progress,
    record_scrape_run_error,
    finish_scrape_run_success,
    finish_scrape_run_partial,
    finish_scrape_run_failed,
)


def post_to_review_queue(job):
    """
    Replace this with your real review queue posting logic.
    Expected return examples:
      {"created_new_review_item": True}
      {"created_new_review_item": False}
    """
    return {"created_new_review_item": True}


def get_mock_scraped_jobs():
    """
    Replace this with your real SmartJobs scrape results.
    """
    return [
        {"job_title": "Senior Project Officer", "is_match": True},
        {"job_title": "Program Director, Brisbane 2032", "is_match": True},
        {"job_title": "Other Role", "is_match": False},
    ]


def run_smartjobs_scrape():
    db = SessionLocal()
    run_id = None

    jobs_seen = 0
    jobs_matched = 0
    review_items_created = 0
    duplicates_skipped = 0
    error_count = 0
    had_non_fatal_errors = False

    try:
        run_id = start_scrape_run(
            db,
            source_name="smartjobs",
            notes="Local test run started",
        )

        scraped_jobs = get_mock_scraped_jobs()

        for job in scraped_jobs:
            jobs_seen += 1

            try:
                if job.get("is_match"):
                    jobs_matched += 1

                    result = post_to_review_queue(job)

                    if result.get("created_new_review_item"):
                        review_items_created += 1
                    else:
                        duplicates_skipped += 1

            except Exception as item_error:
                had_non_fatal_errors = True
                error_count += 1
                record_scrape_run_error(db, run_id, f"Job processing error: {item_error}")

            flush_scrape_run_progress(
                db,
                run_id,
                jobs_seen,
                jobs_matched,
                review_items_created,
                duplicates_skipped,
                error_count,
            )

        if had_non_fatal_errors:
            finish_scrape_run_partial(
                db,
                run_id,
                error_message="Run completed with some item-level errors",
                notes="Local test run finished with partial success",
            )
        else:
            finish_scrape_run_success(
                db,
                run_id,
                notes="Local test run completed successfully",
            )

    except Exception as fatal_error:
        if run_id is not None:
            finish_scrape_run_failed(
                db,
                run_id,
                error_message=fatal_error,
                notes="Local test run failed",
            )
        raise

    finally:
        db.close()


if __name__ == "__main__":
    run_smartjobs_scrape()