from datetime import datetime
from pathlib import Path
from typing import Generator
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import crud
from app.db.session import SessionLocal
from app.services.entity_resolution import process_staged_linkedin_row
from app.services.linkedin_imports import create_import_run, parse_connections_csv, stage_connections
from app.services.linkedin_review_actions import (
    approve_staged_row_create_contact,
    skip_staged_row,
)

BASE_DIR = Path(__file__).resolve().parent
BRISBANE_TZ = ZoneInfo("Australia/Brisbane")

app = FastAPI(title="BD API UI")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def render_page(
    request: Request,
    template_name: str,
    *,
    page_title: str,
    heading: str,
    description: str,
    active_page: str,
    **context,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "page_title": page_title,
            "heading": heading,
            "description": description,
            "active_page": active_page,
            **context,
        },
    )


@app.get("/", response_class=HTMLResponse)
def ui_home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    summary = crud.get_ops_dashboard_summary(db)
    today = datetime.now(BRISBANE_TZ).date()
    smartjobs_runs = crud.list_smartjobs_runs_for_day(db, day=today)
    review_queue_runs = crud.list_review_queue_runs(db, limit=8)
    linkedin_import_runs = crud.list_linkedin_import_runs_ui(db, limit=8)
    attention_items = crud.list_ops_attention_items(db)
    return render_page(
        request,
        "ops_home.html",
        page_title="BD Ops Dashboard",
        heading="",
        description="",
        active_page="ops",
        summary=summary,
        smartjobs_runs=smartjobs_runs,
        review_queue_runs=review_queue_runs,
        linkedin_import_runs=linkedin_import_runs,
        attention_items=attention_items,
        today_date=today.strftime("%Y-%m-%d"),
    )


@app.get("/crm", response_class=HTMLResponse)
def crm_home(request: Request) -> HTMLResponse:
    return render_page(
        request,
        "crm_home.html",
        page_title="CRM",
        heading="CRM",
        description="Manual entry and browsing for organisations, contacts, projects, and notes.",
        active_page="crm",
    )


@app.get("/organisations", response_class=HTMLResponse)
def organisations_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    organisations = crud.list_organisations_ui(db)
    return render_page(
        request,
        "organisations.html",
        page_title="Organisations",
        heading="Organisations",
        description="Add organisations manually and browse the current list.",
        active_page="organisations",
        organisations=organisations,
    )


@app.get("/organisations/{organisation_id}", response_class=HTMLResponse)
def organisation_detail_page(
    request: Request,
    organisation_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    detail = crud.get_organisation_detail_ui(db=db, organisation_id=organisation_id)
    if not detail:
        return RedirectResponse(url="/ui/organisations", status_code=303)

    organisation = detail["organisation"]
    return render_page(
        request,
        "organisation_detail.html",
        page_title=organisation.name,
        heading=organisation.name,
        description="Organisation workspace for contacts, projects, activities, and tasks.",
        active_page="organisations",
        organisation=organisation,
        contacts=detail["contacts"],
        projects=detail["projects"],
        activities=detail["activities"],
        tasks=detail["tasks"],
    )


@app.get("/contacts", response_class=HTMLResponse)
def contacts_page(
    request: Request,
    organisation_id: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return render_page(
        request,
        "contacts.html",
        page_title="Contacts",
        heading="Contacts",
        description="Create and browse contacts linked to organisations.",
        active_page="contacts",
        contacts=crud.list_contacts(db),
        organisations=crud.list_organisations(db),
        selected_organisation_id=organisation_id,
    )


@app.get("/projects", response_class=HTMLResponse)
def projects_page(
    request: Request,
    organisation_id: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return render_page(
        request,
        "projects.html",
        page_title="Projects",
        heading="Projects",
        description="Create and browse projects linked to organisations.",
        active_page="projects",
        projects=crud.list_projects(db),
        organisations=crud.list_organisations(db),
        selected_organisation_id=organisation_id,
    )


@app.get("/activities", response_class=HTMLResponse)
def activities_page(
    request: Request,
    organisation_id: int | None = None,
    contact_id: int | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return render_page(
        request,
        "activities.html",
        page_title="Activities",
        heading="Activities",
        description="Log interactions and browse recent activity.",
        active_page="activities",
        activities=crud.list_activities(db),
        organisations=crud.list_organisations(db),
        contacts=crud.list_contacts(db),
        projects=crud.list_projects(db),
        selected_organisation_id=organisation_id,
        selected_contact_id=contact_id,
        selected_project_id=project_id,
        default_activity_date=datetime.now().strftime("%Y-%m-%dT%H:%M"),
    )


@app.get("/tasks", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    status: str | None = None,
    organisation_id: int | None = None,
    contact_id: int | None = None,
    project_id: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    tasks = crud.list_tasks(
        db,
        status=status,
        organisation_id=organisation_id,
        contact_id=contact_id,
        project_id=project_id,
    )
    return render_page(
        request,
        "tasks.html",
        page_title="Tasks",
        heading="Tasks",
        description="Track open and completed tasks.",
        active_page="tasks",
        tasks=tasks,
        organisations=crud.list_organisations(db),
        contacts=crud.list_contacts(db),
        projects=crud.list_projects(db),
        filters={
            "status": status or "",
            "organisation_id": organisation_id,
            "contact_id": contact_id,
            "project_id": project_id,
        },
    )


@app.post("/tasks/{task_id}/complete")
def task_complete(
    task_id: int,
    status: str | None = Form(default=None),
    organisation_id: int | None = Form(default=None),
    contact_id: int | None = Form(default=None),
    project_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
):
    crud.complete_task(db, task_id)
    params = []
    if status:
        params.append(f"status={status}")
    if organisation_id:
        params.append(f"organisation_id={organisation_id}")
    if contact_id:
        params.append(f"contact_id={contact_id}")
    if project_id:
        params.append(f"project_id={project_id}")

    redirect_url = "/ui/tasks"
    if params:
        redirect_url = f"{redirect_url}?{'&'.join(params)}"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.get("/linkedin/import", response_class=HTMLResponse)
def linkedin_import_page(request: Request) -> HTMLResponse:
    return render_page(
        request,
        "linkedin/import.html",
        page_title="LinkedIn Import",
        heading="LinkedIn Import",
        description="Upload LinkedIn Connections.csv and process staged matches.",
        active_page="linkedin_import",
    )


@app.post("/linkedin/import")
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


@app.get("/linkedin/runs/{run_id}", response_class=HTMLResponse)
def linkedin_run_detail(
    request: Request,
    run_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    run = crud.get_linkedin_import_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="LinkedIn import run not found")

    return render_page(
        request,
        "linkedin/run_detail.html",
        page_title=f"LinkedIn Import Run {run.id}",
        heading=f"LinkedIn Import Run #{run.id}",
        description=f"Imported file: {run.filename}",
        active_page="linkedin_import",
        run=run,
        staged_rows=crud.list_linkedin_connection_staging_rows(db, import_run_id=run_id),
    )


@app.get("/linkedin/review", response_class=HTMLResponse)
def linkedin_review_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return render_page(
        request,
        "linkedin/review.html",
        page_title="LinkedIn Review",
        heading="LinkedIn Review",
        description="Review flagged LinkedIn staging rows and approve or skip them.",
        active_page="linkedin_review",
        pending_rows=crud.list_pending_linkedin_reviews(db),
        organisations=crud.list_organisations(db),
    )


@app.post("/linkedin/review/{staging_row_id}/approve")
async def linkedin_review_approve(
    staging_row_id: int,
    organisation_id: int = Form(...),
    reviewer: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    row = crud.get_linkedin_connection_staging_row(db, staging_row_id)
    if not row:
        raise HTTPException(status_code=404, detail="LinkedIn staging row not found")

    organisation = crud.get_organisation(db, organisation_id)
    if not organisation:
        raise HTTPException(status_code=400, detail="Selected organisation not found")

    crud.update_linkedin_connection_staging_row(
        db,
        staging_row_id,
        {
            "matched_organisation_id": organisation.id,
            "matched_organisation_name": organisation.name,
            "review_notes": row.review_notes,
        },
    )
    approve_staged_row_create_contact(
        db=db,
        staged_row_id=staging_row_id,
        organisation_id=organisation.id,
        reviewer=reviewer,
    )
    return RedirectResponse(url="/ui/linkedin/review", status_code=303)


@app.post("/linkedin/review/{staging_row_id}/skip")
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
        staged_row_id=staging_row_id,
        reviewer=reviewer,
        note=note,
    )
    return RedirectResponse(url="/ui/linkedin/review", status_code=303)


@app.get("/smartjobs", response_class=HTMLResponse)
def smartjobs_results_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    scrape_runs = db.execute(
        text(
            """
            select id, started_at, finished_at, status, jobs_seen, jobs_matched,
                   review_items_created, duplicates_skipped, error_count, error_message
            from public.scrape_runs
            where source_name = 'smartjobs'
            order by started_at desc
            limit 20
            """
        )
    ).mappings().all()
    review_items = db.execute(
        text(
            """
            select id, review_status, job_title, scraped_organisation,
                   scraped_contact_name, scraped_contact_email, scraped_contact_phone,
                   best_score, job_url, created_at, updated_at
            from public.review_queue
            where source_type = 'smartjobs'
            order by updated_at desc, id desc
            limit 20
            """
        )
    ).mappings().all()
    return render_page(
        request,
        "smartjobs/results.html",
        page_title="SmartJobs Results",
        heading="SmartJobs Results",
        description="Recent scraper runs and the job content handed to the SmartJobs Review Queue.",
        active_page="smartjobs_results",
        scrape_runs=scrape_runs,
        review_items=review_items,
    )


@app.get("/smartjobs/review-queue", response_class=HTMLResponse)
def smartjobs_review_queue_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    organisations = crud.list_organisations(db)
    organisation_options = [
        {"id": organisation.id, "name": organisation.name}
        for organisation in organisations
    ]
    return render_page(
        request,
        "smartjobs/review_queue.html",
        page_title="SmartJobs Review Queue",
        heading="SmartJobs Review Queue",
        description="Review SmartJobs contacts and organisations without mixing them with LinkedIn workflows.",
        active_page="smartjobs_review_queue",
        organisation_options=organisation_options,
    )
