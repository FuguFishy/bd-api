from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import crud
from app.ui.core import get_db, templates
from app.ui.services.tasks import build_task_page_context

router = APIRouter(prefix="/tasks", tags=["tasks-ui"])


@router.get("", response_class=HTMLResponse)
def tasks_page(
    request: Request,
    status: str | None = None,
    organisation_id: int | None = None,
    contact_id: int | None = None,
    project_id: int | None = None,
    include_completed: bool = False,
    db: Session = Depends(get_db),
):
    tasks = crud.list_tasks(
        db=db,
        status=status,
        organisation_id=organisation_id,
        contact_id=contact_id,
        project_id=project_id,
        include_completed=include_completed,
    )
    organisations = crud.list_organisations(db)
    contacts = crud.list_contacts(db)
    projects = crud.list_projects(db)

    task_groups = build_task_page_context(tasks)

    return templates.TemplateResponse(
        request=request,
        name="tasks.html",
        context={
            "page_title": "Tasks",
            "heading": "Tasks",
            "description": "Track open follow-ups, due dates, and completed actions.",
            "active_page": "tasks",
            "tasks": tasks,
            "overdue_tasks": task_groups["overdue_tasks"],
            "due_soon_tasks": task_groups["due_soon_tasks"],
            "organisations": organisations,
            "contacts": contacts,
            "projects": projects,
            "selected_status": status,
            "selected_organisation_id": organisation_id,
            "selected_contact_id": contact_id,
            "selected_project_id": project_id,
            "include_completed": include_completed,
        },
    )


@router.post("/{task_id}/complete")
async def task_complete(
    task_id: int,
    db: Session = Depends(get_db),
):
    crud.complete_task(db, task_id)
    return RedirectResponse(url="/ui/tasks", status_code=303)