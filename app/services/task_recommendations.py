from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db import models


def build_source_key(rule_name: str, contact_id: int | None, organisation_id: int | None) -> str:
    return f"{rule_name}:{contact_id or 0}:{organisation_id or 0}"


def find_existing_open_task(db: Session, source_key: str):
    return (
        db.query(models.Task)
        .filter(models.Task.source_key == source_key)
        .filter(models.Task.status != "completed")
        .first()
    )


def create_task_if_needed(
    db: Session,
    *,
    contact_id: int | None,
    organisation_id: int | None,
    project_id: int | None,
    activity_id: int | None,
    task_type: str,
    reason: str,
    priority: str = "medium",
    owner: str | None = None,
    rule_name: str,
):
    source_key = build_source_key(rule_name, contact_id, organisation_id)
    existing = find_existing_open_task(db, source_key)
    if existing:
        return existing, False

    task = models.Task(
        contact_id=contact_id,
        organisation_id=organisation_id,
        project_id=project_id,
        activity_id=activity_id,
        task_type=task_type,
        reason=reason,
        priority=priority,
        status="open",
        due_date=date.today() + timedelta(days=7),
        owner=owner,
        source_type="linkedin_rule",
        source_key=source_key,
        recommended_by_rule=rule_name,
    )
    db.add(task)
    db.flush()
    return task, True