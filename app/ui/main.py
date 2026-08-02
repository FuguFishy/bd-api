from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.db import crud
from app.ui.core import BASE_DIR, get_db, templates
from app.ui.routes.linkedin import router as linkedin_router
from app.ui.routes.tasks import router as tasks_router

app = FastAPI(title="BD API UI")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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
    recent_runs = crud.list_recent_workflow_runs(db, limit=20)
    attention_items = crud.list_ops_attention_items(db)

    return render_page(
        request,
        "ops_home.html",
        page_title="BD Ops Dashboard",
        heading="BD Ops Dashboard",
        description="SmartJobs runs, review queue, and workflow issues.",
        active_page="ops",
        summary=summary,
        recent_runs=recent_runs,
        attention_items=attention_items,
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
def organisations_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
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
        raise HTTPException(status_code=404, detail="Organisation not found")

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

@app.post("/organisations/{organisation_id}/edit")
async def organisation_edit_submit(
    organisation_id: int,
    name: str = Form(...),
    short_name: str | None = Form(default=None),
    sector: str | None = Form(default=None),
    tier: str | None = Form(default=None),
    account_status: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    crud.update_organisation(
        db,
        organisation_id,
        {
            "name": name,
            "short_name": short_name,
            "sector": sector,
            "tier": tier,
            "account_status": account_status,
        },
    )
    return RedirectResponse(
        url=f"/organisations/{organisation_id}",
        status_code=303,
    )


@app.get("/contacts", response_class=HTMLResponse)
def contacts_page(
    request: Request,
    organisation_id: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    contacts = crud.list_contacts(db)
    organisations = crud.list_organisations(db)

    return render_page(
        request,
        "contacts.html",
        page_title="Contacts",
        heading="Contacts",
        description="Create and browse contacts linked to organisations.",
        active_page="contacts",
        contacts=contacts,
        organisations=organisations,
        selected_organisation_id=organisation_id,
    )


@app.get("/projects", response_class=HTMLResponse)
def projects_page(
    request: Request,
    organisation_id: int | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    projects = crud.list_projects(db)
    organisations = crud.list_organisations(db)

    return render_page(
        request,
        "projects.html",
        page_title="Projects",
        heading="Projects",
        description="Create and browse projects linked to organisations.",
        active_page="projects",
        projects=projects,
        organisations=organisations,
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
    activities = crud.list_activities(db)
    organisations = crud.list_organisations(db)
    contacts = crud.list_contacts(db)
    projects = crud.list_projects(db)

    return render_page(
        request,
        "activities.html",
        page_title="Activities",
        heading="Activities",
        description="Log interactions and browse recent activity.",
        active_page="activities",
        activities=activities,
        organisations=organisations,
        contacts=contacts,
        projects=projects,
        selected_organisation_id=organisation_id,
        selected_contact_id=contact_id,
        selected_project_id=project_id,
        default_activity_date=datetime.now().strftime("%Y-%m-%dT%H:%M"),
    )


app.include_router(tasks_router)
app.include_router(linkedin_router)