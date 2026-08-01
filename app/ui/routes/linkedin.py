from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import crud
from app.services.entity_resolution import process_staged_linkedin_row
from app.services.linkedin_imports import (
    create_import_run,
    parse_connections_csv,
    stage_connections,
)
from app.services.linkedin_review_actions import skip_staged_row
from app.ui.core import get_db, templates
from app.ui.services.linkedin_review import approve_reviewed_staging_row

router = APIRouter(prefix="/linkedin", tags=["linkedin-ui"])


@router.get("/import", response_class=HTMLResponse)
def linkedin_import_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="linkedin/import.html",
        context={
            "page_title": "LinkedIn Import",
            "heading": "LinkedIn Import",
            "description": "Upload LinkedIn Connections.csv and process staged matches.",
            "active_page": "linkedin_import",
        },
    )


@router.post("/import")
async def linkedin_import_submit(
    file: UploadFile = File(...),
    uploaded_by: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()

    run = create_import_run(db, filename=file.filename, uploaded_by=uploaded_by)
    rows = parse_connections_csv(file_bytes)
    staged_rows = stage_connections(db, run.id, rows)

    for row in staged_rows:
        process_staged_linkedin_row(db, row)

    return RedirectResponse(url=f"/ui/linkedin/runs/{run.id}", status_code=303)


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def linkedin_run_detail(
    request: Request,
    run_id: int,
    db: Session = Depends(get_db),
):
    run = crud.get_linkedin_import_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="LinkedIn import run not found")

    staged_rows = crud.list_linkedin_connection_staging_rows(db, import_run_id=run_id)

    return templates.TemplateResponse(
        request=request,
        name="linkedin/run_detail.html",
        context={
            "page_title": f"LinkedIn Import Run {run.id}",
            "heading": f"LinkedIn Import Run #{run.id}",
            "description": f"Imported file: {run.filename}",
            "active_page": "linkedin_import",
            "run": run,
            "staged_rows": staged_rows,
        },
    )


@router.get("/review", response_class=HTMLResponse)
def linkedin_review_page(
    request: Request,
    db: Session = Depends(get_db),
):
    pending_rows = crud.list_pending_linkedin_reviews(db)
    organisations = crud.list_organisations(db)

    return templates.TemplateResponse(
        request=request,
        name="linkedin/review.html",
        context={
            "page_title": "LinkedIn Review",
            "heading": "LinkedIn Review",
            "description": "Review flagged LinkedIn staging rows and approve or skip them.",
            "active_page": "linkedin_review",
            "pending_rows": pending_rows,
            "organisations": organisations,
        },
    )


@router.post("/review/{staging_row_id}/approve")
async def linkedin_review_approve(
    staging_row_id: int,
    organisation_id: int | None = Form(default=None),
    reviewer: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    approve_reviewed_staging_row(
        db=db,
        staging_row_id=staging_row_id,
        organisation_id=organisation_id,
        reviewer=reviewer,
    )
    return RedirectResponse(url="/ui/linkedin/review", status_code=303)


@router.post("/review/{staging_row_id}/skip")
async def linkedin_review_skip(
    staging_row_id: int,
    reviewer: str | None = Form(default=None),
    note: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    row = crud.get_linkedin_connection_staging_row(db, staging_row_id)
    if not row:
        raise HTTPException(status_code=404, detail="LinkedIn staging row not found")

    skip_staged_row(
        db=db,
        staging_row_id=staging_row_id,
        reviewer=reviewer,
        note=note,
    )
    return RedirectResponse(url="/ui/linkedin/review", status_code=303)