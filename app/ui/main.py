import csv
import os
from datetime import date, datetime, timedelta
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
from app.schemas.activities import ActivityCreate
from app.schemas.contacts import ContactCreate
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


def clean_optional(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def optional_id(value: str | None) -> int | None:
    return int(value) if value else None


def optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None




REPORT_PERIODS = {
    "week": "Week",
    "month": "Month",
    "quarter": "Quarter",
    "financial_ytd": "Financial YTD",
    "financial_year": "Financial Year",
}


def start_of_financial_year(value: date) -> date:
    return date(value.year if value.month >= 7 else value.year - 1, 7, 1)


def report_period_range(period: str, as_at: date) -> tuple[date, date, str]:
    if period == "week":
        start = as_at - timedelta(days=as_at.weekday())
        return start, start + timedelta(days=7), f"Week beginning {start:%d %b %Y}"

    if period == "month":
        start = as_at.replace(day=1)
        end = (
            date(start.year + 1, 1, 1)
            if start.month == 12
            else date(start.year, start.month + 1, 1)
        )
        return start, end, start.strftime("%B %Y")

    if period == "quarter":
        quarter_start_month = ((as_at.month - 1) // 3) * 3 + 1
        start = date(as_at.year, quarter_start_month, 1)
        end = (
            date(as_at.year + 1, 1, 1)
            if quarter_start_month == 10
            else date(as_at.year, quarter_start_month + 3, 1)
        )
        quarter = ((as_at.month - 1) // 3) + 1
        return start, end, f"Q{quarter} {as_at.year}"

    financial_year_start = start_of_financial_year(as_at)
    financial_year_end = date(financial_year_start.year + 1, 7, 1)
    financial_year_label = f"FY{financial_year_end.year}"

    if period == "financial_year":
        return financial_year_start, financial_year_end, financial_year_label

    return (
        financial_year_start,
        as_at + timedelta(days=1),
        f"{financial_year_label} to {as_at:%d %b %Y}",
    )

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
    today = datetime.now(BRISBANE_TZ).date()
    daily = crud.get_daily_bd_actions(db=db, today=today, contact_limit=25)
    smartjobs_runs = crud.list_smartjobs_runs_for_day(db, day=today)
    linkedin_import_runs = crud.list_linkedin_import_runs_ui(db, limit=3)

    return render_page(
        request,
        "ops_home.html",
        page_title="Daily BD Actions",
        heading="",
        description="",
        active_page="ops",
        daily=daily,
        smartjobs_runs=smartjobs_runs,
        linkedin_import_runs=linkedin_import_runs,
        today_date=today.strftime("%d %b %Y"),
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



@app.get("/reports/linkedin-opportunities", response_class=HTMLResponse)
def linkedin_opportunities_report_page(
    request: Request,
    organisation_id: int | None = None,
    report_date: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        selected_report_date = (
            date.fromisoformat(report_date)
            if report_date
            else datetime.now(BRISBANE_TZ).date()
        )
    except ValueError:
        selected_report_date = datetime.now(BRISBANE_TZ).date()

    daily_report = crud.get_reports_daily_linkedin_actions(
        db,
        report_date=selected_report_date,
        organisation_id=organisation_id,
        connect_limit=25,
    )
    organisations = crud.list_organisations(db)

    return render_page(
        request,
        "linkedin_opportunities.html",
        page_title="Daily LinkedIn actions",
        heading="Daily LinkedIn actions",
        description=(
            "New APS Jobs and SmartJobs contacts needing a LinkedIn "
            "connection request, plus pending invitation follow-up."
        ),
        active_page="reports",
        organisations=organisations,
        selected_organisation_id=organisation_id,
        report_date=selected_report_date.isoformat(),
        connect_today=daily_report["connect_today"],
        pending_follow_up=daily_report["pending_follow_up"],
        eligible_total=daily_report["eligible_total"],
        new_today_total=daily_report["new_today_total"],
        backlog_total=daily_report["backlog_total"],
        pending_total=daily_report["pending_total"],
    )

def _linkedin_opportunities_redirect(
    organisation_id: int | None,
    report_date: str | None,
) -> RedirectResponse:
    params: list[str] = []

    if organisation_id:
        params.append(f"organisation_id={organisation_id}")

    if report_date:
        params.append(f"report_date={report_date}")

    query = f"?{'&'.join(params)}" if params else ""

    return RedirectResponse(
        url=f"/ui/reports/linkedin-opportunities{query}",
        status_code=303,
    )

@app.post(
    "/reports/linkedin-opportunities/{contact_id}/mark-invitation-sent"
)
def mark_linkedin_invitation_sent(
    contact_id: int,
    organisation_id: int | None = Form(default=None),
    report_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    contact = db.execute(
        text(
            """
            select
                c.id,
                c.organisation_id
            from public.contacts c
            where c.id = :contact_id
            """
        ),
        {"contact_id": contact_id},
    ).mappings().first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    try:
        db.execute(
            text(
                """
                update public.contacts
                set
                    linkedin_connection_status = 'pending',
                    linkedin_invitation_sent_at = now(),
                    updated_at = now()
                where id = :contact_id
                """
            ),
            {"contact_id": contact_id},
        )

        db.execute(
            text(
                """
                insert into public.activities (
                    contact_id,
                    organisation_id,
                    activity_type,
                    activity_date,
                    outcome,
                    notes,
                    logged_by
                )
                values (
                    :contact_id,
                    :organisation_id,
                    'linkedin_invitation_sent',
                    now(),
                    'Pending LinkedIn connection confirmation',
                    'Invitation marked as sent from LinkedIn connection opportunities report.',
                    'bd-api'
                )
                """
            ),
            {
                "contact_id": contact_id,
                "organisation_id": contact["organisation_id"],
            },
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return _linkedin_opportunities_redirect(
        organisation_id=organisation_id,
        report_date=report_date,
    )

@app.post(
    "/reports/linkedin-opportunities/{contact_id}/update-invitation-status"
)
def update_linkedin_invitation_status(
    contact_id: int,
    action: str = Form(...),
    organisation_id: int | None = Form(default=None),
    report_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    action_config = {
        "still_pending": {
            "contact_status": "pending",
            "activity_type": "linkedin_invitation_follow_up",
            "outcome": "Pending LinkedIn connection confirmation",
            "requires_invitation": True,
            "notes": (
                "LinkedIn invitation follow-up recorded from LinkedIn "
                "connection opportunities report."
            ),
        },
        "connected": {
            "contact_status": "connected",
            "activity_type": "linkedin_connection_confirmed",
            "outcome": "LinkedIn connection confirmed",
            "requires_invitation": True,
            "notes": (
                "LinkedIn connection confirmed from LinkedIn connection "
                "opportunities report."
            ),
        },
        "connection_declined": {
            "contact_status": "not_connected",
            "activity_type": "linkedin_connection_not_connected",
            "outcome": "Connection Declined",
            "requires_invitation": True,
            "notes": (
                "LinkedIn invitation marked as declined from LinkedIn "
                "connection opportunities report."
            ),
        },
        "not_invited_to_connect": {
            "contact_status": "not_connected",
            "activity_type": "linkedin_connection_not_connected",
            "outcome": "Not Invited to Connect",
            "requires_invitation": False,
            "notes": (
                "Contact was reviewed and not invited to connect from "
                "LinkedIn connection opportunities report."
            ),
        },
        "not_on_linkedin": {
            "contact_status": "not_connected",
            "activity_type": "linkedin_connection_not_connected",
            "outcome": "Not on LinkedIn",
            "requires_invitation": False,
            "notes": (
                "No valid LinkedIn profile was identified for this contact "
                "from the LinkedIn connection opportunities report."
            ),
        },
    }

    config = action_config.get(action)
    if not config:
        raise HTTPException(
            status_code=400,
            detail="Invalid LinkedIn invitation status action",
        )

    contact = db.execute(
        text(
            """
            select
                c.id,
                c.organisation_id,
                c.linkedin_invitation_sent_at
            from public.contacts c
            where c.id = :contact_id
            """
        ),
        {"contact_id": contact_id},
    ).mappings().first()

    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    if config["requires_invitation"] and not contact[
        "linkedin_invitation_sent_at"
    ]:
        raise HTTPException(
            status_code=409,
            detail="Contact has no recorded LinkedIn invitation",
        )

    try:
        db.execute(
            text(
                """
                update public.contacts
                set
                    linkedin_connection_status = :contact_status,
                    updated_at = now()
                where id = :contact_id
                """
            ),
            {
                "contact_id": contact_id,
                "contact_status": config["contact_status"],
            },
        )

        db.execute(
            text(
                """
                insert into public.activities (
                    contact_id,
                    organisation_id,
                    activity_type,
                    activity_date,
                    outcome,
                    notes,
                    logged_by
                )
                values (
                    :contact_id,
                    :organisation_id,
                    :activity_type,
                    now(),
                    :outcome,
                    :notes,
                    'bd-api'
                )
                """
            ),
            {
                "contact_id": contact_id,
                "organisation_id": contact["organisation_id"],
                "activity_type": config["activity_type"],
                "outcome": config["outcome"],
                "notes": config["notes"],
            },
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return _linkedin_opportunities_redirect(
        organisation_id=organisation_id,
        report_date=report_date,
    )

@app.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    period: str = "financial_ytd",
    as_at: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if period not in REPORT_PERIODS:
        period = "financial_ytd"

    try:
        as_at_date = (
            date.fromisoformat(as_at)
            if as_at
            else datetime.now(BRISBANE_TZ).date()
        )
    except ValueError:
        as_at_date = datetime.now(BRISBANE_TZ).date()

    period_start, period_end, period_label = report_period_range(period, as_at_date)
    activity_by_organisation = crud.get_reports_activity_by_organisation(
        db, period_start, period_end
    )
    activity_by_type = crud.get_reports_activity_by_type(
        db, period_start, period_end
    )
    activity_by_contact = crud.get_reports_activity_by_contact(
        db, period_start, period_end
    )
    linkedin_by_organisation = crud.get_reports_linkedin_connections_by_organisation(db)
    organisations_needing_attention = crud.get_reports_organisations_needing_attention(
        db, as_at_date
    )

    return render_page(
        request,
        "reports.html",
        page_title="Reports",
        heading="Reports",
        description="Activity, relationship coverage, and account attention indicators.",
        active_page="reports",
        report_periods=REPORT_PERIODS,
        selected_period=period,
        as_at_date=as_at_date.isoformat(),
        period_label=period_label,
        total_activities=sum(row["activity_count"] for row in activity_by_organisation),
        activity_by_organisation=activity_by_organisation,
        activity_by_type=activity_by_type,
        activity_by_contact=activity_by_contact,
        linkedin_by_organisation=linkedin_by_organisation,
        organisations_needing_attention=organisations_needing_attention,
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


@app.post("/organisations")
def create_organisation_from_form(
    name: str = Form(...),
    short_name: str | None = Form(default=None),
    sector: str | None = Form(default=None),
    tier: str | None = Form(default=None),
    account_status: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    crud.create_organisation(
        db,
        {
            "name": name.strip(),
            "short_name": clean_optional(short_name),
            "sector": clean_optional(sector),
            "tier": clean_optional(tier),
            "account_status": clean_optional(account_status),
            "notes": clean_optional(notes),
        },
    )
    return RedirectResponse(url="/ui/organisations", status_code=303)


@app.get("/organisations/{organisation_id}/edit", response_class=HTMLResponse)
def edit_organisation_page(
    request: Request,
    organisation_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    organisation = crud.get_organisation(db, organisation_id)
    if not organisation:
        return RedirectResponse(url="/ui/organisations", status_code=303)

    return render_page(
        request,
        "organisation_edit.html",
        page_title=f"Edit {organisation.name}",
        heading="Edit Organisation",
        description="Update account details for this organisation.",
        active_page="organisations",
        organisation=organisation,
    )


@app.post("/organisations/{organisation_id}/edit")
def update_organisation_from_form(
    organisation_id: int,
    name: str = Form(...),
    short_name: str | None = Form(default=None),
    sector: str | None = Form(default=None),
    tier: str | None = Form(default=None),
    account_status: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    last_contact_date: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    crud.update_organisation(
        db,
        organisation_id,
        {
            "name": name.strip(),
            "short_name": clean_optional(short_name),
            "sector": clean_optional(sector),
            "tier": clean_optional(tier),
            "account_status": clean_optional(account_status),
            "notes": clean_optional(notes),
            "last_contact_date": optional_date(last_contact_date),
        },
    )
    return RedirectResponse(
        url=f"/ui/organisations/{organisation_id}",
        status_code=303,
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


@app.post("/contacts")
def create_contact_from_form(
    organisation_id: int = Form(...),
    first_name: str | None = Form(default=None),
    last_name: str | None = Form(default=None),
    full_name: str = Form(...),
    position_title: str | None = Form(default=None),
    department: str | None = Form(default=None),
    email: str | None = Form(default=None),
    linkedin_profile_url: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    clean_full_name = full_name.strip()
    name_parts = clean_full_name.split(maxsplit=1)

    clean_first_name = (first_name or "").strip() or name_parts[0]
    clean_last_name = (last_name or "").strip()
    if not clean_last_name and len(name_parts) > 1:
        clean_last_name = name_parts[1]

    payload = ContactCreate(
        organisation_id=organisation_id,
        first_name=clean_first_name,
        last_name=clean_last_name,
        full_name=clean_full_name,
        position_title=position_title.strip() if position_title else None,
        department=department.strip() if department else None,
        email=email.strip() if email else None,
        linkedin_profile_url=(
            linkedin_profile_url.strip()
            if linkedin_profile_url
            else None
        ),
    )

    crud.create_contact(db, payload)
    return RedirectResponse(
        url=f"/ui/contacts?organisation_id={organisation_id}",
        status_code=303,
    )


@app.get("/contacts/{contact_id}/edit", response_class=HTMLResponse)
def edit_contact_page(
    request: Request,
    contact_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    contact = crud.get_contact(db, contact_id)
    if not contact:
        return RedirectResponse(url="/ui/contacts", status_code=303)

    return render_page(
        request,
        "contact_edit.html",
        page_title=f"Edit {contact.full_name or contact.first_name}",
        heading="Edit Contact",
        description="Update contact details and organisation link.",
        active_page="contacts",
        contact=contact,
        organisations=crud.list_organisations(db),
    )


@app.post("/contacts/{contact_id}/edit")
def update_contact_from_form(
    contact_id: int,
    organisation_id: int = Form(...),
    first_name: str | None = Form(default=None),
    last_name: str | None = Form(default=None),
    full_name: str = Form(...),
    position_title: str | None = Form(default=None),
    department: str | None = Form(default=None),
    email: str | None = Form(default=None),
    linkedin_profile_url: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    clean_full_name = full_name.strip()
    name_parts = clean_full_name.split(maxsplit=1)

    clean_first_name = clean_optional(first_name) or name_parts[0]
    clean_last_name = clean_optional(last_name)
    if not clean_last_name and len(name_parts) > 1:
        clean_last_name = name_parts[1]

    crud.update_contact(
        db,
        contact_id,
        {
            "organisation_id": organisation_id,
            "first_name": clean_first_name,
            "last_name": clean_last_name or "",
            "full_name": clean_full_name,
            "position_title": clean_optional(position_title),
            "department": clean_optional(department),
            "email": clean_optional(email),
            "linkedin_profile_url": clean_optional(linkedin_profile_url),
        },
    )

    return RedirectResponse(
        url=f"/ui/contacts?organisation_id={organisation_id}",
        status_code=303,
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


@app.post("/projects")
def create_project_from_form(
    organisation_id: int = Form(...),
    contact_id: str | None = Form(default=None),
    name: str = Form(...),
    project_type: str | None = Form(default=None),
    status: str | None = Form(default=None),
    opportunity_signal: str | None = Form(default=None),
    strategic_importance: str | None = Form(default=None),
    start_date: str | None = Form(default=None),
    end_date: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    crud.create_project(
        db,
        {
            "organisation_id": organisation_id,
            "contact_id": optional_id(contact_id),
            "name": name.strip(),
            "project_type": clean_optional(project_type),
            "status": clean_optional(status),
            "opportunity_signal": clean_optional(opportunity_signal),
            "strategic_importance": clean_optional(strategic_importance),
            "start_date": optional_date(start_date),
            "end_date": optional_date(end_date),
            "notes": clean_optional(notes),
        },
    )
    return RedirectResponse(
        url=f"/ui/projects?organisation_id={organisation_id}",
        status_code=303,
    )


@app.get("/projects/{project_id}/edit", response_class=HTMLResponse)
def edit_project_page(
    request: Request,
    project_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    project = crud.get_project(db, project_id)
    if not project:
        return RedirectResponse(url="/ui/projects", status_code=303)

    return render_page(
        request,
        "project_edit.html",
        page_title=f"Edit {project.name}",
        heading="Edit Project",
        description="Update project, opportunity, and relationship details.",
        active_page="projects",
        project=project,
        organisations=crud.list_organisations(db),
        contacts=crud.list_contacts(db),
    )


@app.post("/projects/{project_id}/edit")
def update_project_from_form(
    project_id: int,
    organisation_id: int = Form(...),
    contact_id: str | None = Form(default=None),
    name: str = Form(...),
    project_type: str | None = Form(default=None),
    status: str | None = Form(default=None),
    opportunity_signal: str | None = Form(default=None),
    strategic_importance: str | None = Form(default=None),
    start_date: str | None = Form(default=None),
    end_date: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    crud.update_project(
        db,
        project_id,
        {
            "organisation_id": organisation_id,
            "contact_id": optional_id(contact_id),
            "name": name.strip(),
            "project_type": clean_optional(project_type),
            "status": clean_optional(status),
            "opportunity_signal": clean_optional(opportunity_signal),
            "strategic_importance": clean_optional(strategic_importance),
            "start_date": optional_date(start_date),
            "end_date": optional_date(end_date),
            "notes": clean_optional(notes),
        },
    )
    return RedirectResponse(
        url=f"/ui/projects?organisation_id={organisation_id}",
        status_code=303,
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


@app.post("/activities")
def create_activity_from_form(
    organisation_id: str | None = Form(default=None),
    contact_id: str | None = Form(default=None),
    project_id: str | None = Form(default=None),
    activity_type: str = Form(...),
    activity_date: str = Form(...),
    outcome: str | None = Form(default=None),
    logged_by: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    def optional_id(value: str | None) -> int | None:
        return int(value) if value else None

    payload = ActivityCreate(
        organisation_id=optional_id(organisation_id),
        contact_id=optional_id(contact_id),
        project_id=optional_id(project_id),
        activity_type=activity_type.strip(),
        activity_date=activity_date,
        outcome=outcome.strip() if outcome else None,
        logged_by=logged_by.strip() if logged_by else None,
        notes=notes.strip() if notes else None,
    )
    crud.create_activity(db, payload)
    return RedirectResponse(url="/ui/activities", status_code=303)


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


SMARTJOBS_AUDIT_FILE = Path(
    os.getenv(
        "SMARTJOBS_ALL_RESULTS_FILE",
        "/home/ubuntu/smartjobs/data/smartjobs_all_results.csv",
    )
)
SMARTJOBS_AUDIT_COLUMNS = [
    "job_title",
    "organisation",
    "matched_client",
    "match_score",
    "match_status",
    "contact_name",
    "contact_phone",
    "contact_email",
    "close_date",
    "job_url",
    "occupational_group",
    "date_scraped",
]


def load_smartjobs_audit_rows(
    status: str = "",
    query: str = "",
    limit: int = 200,
) -> tuple[list[dict[str, str]], str]:
    if not SMARTJOBS_AUDIT_FILE.exists():
        return [], ""

    try:
        with SMARTJOBS_AUDIT_FILE.open(
            encoding="utf-8-sig",
            newline="",
        ) as audit_file:
            reader = csv.DictReader(audit_file)
            if not reader.fieldnames:
                return [], "The SmartJobs audit file has no header row."

            rows = []
            status = status.strip().lower()
            query = query.strip().lower()

            for raw_row in reader:
                row = {
                    column: (raw_row.get(column) or "").strip()
                    for column in SMARTJOBS_AUDIT_COLUMNS
                }

                if status and row["match_status"].lower() != status:
                    continue

                if query:
                    searchable = " ".join(
                        row[column].lower()
                        for column in (
                            "job_title",
                            "organisation",
                            "matched_client",
                            "occupational_group",
                            "match_status",
                        )
                    )
                    if query not in searchable:
                        continue

                rows.append(row)

            rows.sort(
                key=lambda row: (
                    row["date_scraped"],
                    row["close_date"],
                    row["job_title"],
                ),
                reverse=True,
            )
            return rows[:limit], ""
    except (OSError, csv.Error) as exc:
        return [], f"Could not read the SmartJobs audit file: {exc}"



APS_AUDIT_FILE = Path(
    os.getenv(
        "APS_CANDIDATE_REVIEW_FILE",
        "/home/ubuntu/apsjobs/data/apsjobs_candidate_review.csv",
    )
)
APS_AUDIT_COLUMNS = [
    "job_id",
    "job_title",
    "organisation",
    "matched_client",
    "salary",
    "location",
    "close_date",
    "date_scraped",
    "job_category",
    "aps_classification",
    "agency_employment_act",
    "title_candidate_category",
    "title_candidate_reason",
    "review_recommended",
    "contact_name",
    "contact_email",
    "contact_phone",
    "job_url",
]


def load_aps_audit_rows(
    category: str = "",
    query: str = "",
    limit: int = 200,
) -> tuple[list[dict[str, str]], str]:
    if not APS_AUDIT_FILE.exists():
        return [], ""

    try:
        with APS_AUDIT_FILE.open(
            encoding="utf-8-sig",
            newline="",
        ) as audit_file:
            reader = csv.DictReader(audit_file)
            if not reader.fieldnames:
                return [], "The APS candidate-review file has no header row."

            rows = []
            category = category.strip().lower()
            query = query.strip().lower()

            for raw_row in reader:
                row = {
                    column: (raw_row.get(column) or "").strip()
                    for column in APS_AUDIT_COLUMNS
                }

                if category and row["title_candidate_category"].lower() != category:
                    continue

                if query:
                    searchable = " ".join(
                        row[column].lower()
                        for column in (
                            "job_id",
                            "job_title",
                            "organisation",
                            "matched_client",
                            "job_category",
                            "aps_classification",
                            "title_candidate_category",
                            "title_candidate_reason",
                        )
                    )
                    if query not in searchable:
                        continue

                rows.append(row)

            rows.sort(
                key=lambda row: (
                    row["close_date"],
                    row["job_title"],
                ),
                reverse=True,
            )
            return rows[:limit], ""
    except (OSError, csv.Error) as exc:
        return [], f"Could not read the APS candidate-review file: {exc}"


@app.get("/aps-jobs", response_class=HTMLResponse)
def aps_jobs_results_page(
    request: Request,
    category: str = "",
    q: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    audit_rows, audit_error = load_aps_audit_rows(
        category=category,
        query=q,
    )
    scrape_runs = db.execute(
        text(
            """
            select
                id,
                started_at,
                finished_at,
                status,
                jobs_seen,
                jobs_matched,
                review_items_created,
                duplicates_skipped,
                error_count,
                error_message,
                notes
            from public.scrape_runs
            where source_name = 'aps_jobs'
            order by started_at desc
            limit 20
            """
        )
    ).mappings().all()

    review_items = db.execute(
        text(
            """
            select
                id,
                review_status,
                source_record_key,
                job_title,
                scraped_organisation,
                scraped_contact_name,
                scraped_contact_email,
                scraped_contact_phone,
                job_url,
                source_payload,
                review_action,
                review_notes,
                resolved_by,
                resolved_at,
                created_at,
                updated_at
            from public.review_queue
            where source_type = 'aps_jobs'
            order by updated_at desc, id desc
            limit 100
            """
        )
    ).mappings().all()

    return render_page(
        request,
        "aps_jobs/results.html",
        page_title="APS Jobs Results",
        heading="APS Jobs Results",
        description="APS candidate results and their review-queue status.",
        active_page="aps_jobs_results",
        scrape_runs=scrape_runs,
        review_items=review_items,
        audit_rows=audit_rows,
        audit_error=audit_error,
        audit_category=category.strip().lower(),
        audit_query=q.strip(),
        audit_file_exists=APS_AUDIT_FILE.exists(),
    )


@app.get("/aps-jobs/review-queue", response_class=HTMLResponse)
def aps_jobs_review_queue_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    organisation_options = [
        {"id": organisation.id, "name": organisation.name}
        for organisation in crud.list_organisations(db)
    ]
    return render_page(
        request,
        "aps_jobs/review_queue.html",
        page_title="APS Jobs Review Queue",
        heading="APS Jobs Review Queue",
        description="Approve APS candidates first, then explicitly link or create CRM contacts under an existing organisation.",
        active_page="aps_jobs_review_queue",
        organisation_options=organisation_options,
    )



@app.get("/smartjobs", response_class=HTMLResponse)
def smartjobs_results_page(
    request: Request,
    status: str = "",
    q: str = "",
    db: Session = Depends(get_db),
) -> HTMLResponse:
    audit_rows, audit_error = load_smartjobs_audit_rows(
        status=status,
        query=q,
    )
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
        audit_rows=audit_rows,
        audit_error=audit_error,
        audit_status=status.strip().lower(),
        audit_query=q.strip(),
        audit_file_exists=SMARTJOBS_AUDIT_FILE.exists(),
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
