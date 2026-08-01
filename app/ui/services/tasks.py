from datetime import date, timedelta
from typing import Any


def build_task_page_context(tasks: list[Any]) -> dict[str, list[Any]]:
    today = date.today()
    soon_cutoff = today + timedelta(days=7)

    overdue_tasks = [
        task
        for task in tasks
        if getattr(task, "due_date", None)
        and getattr(task, "completed_at", None) is None
        and task.due_date < today
    ]

    due_soon_tasks = [
        task
        for task in tasks
        if getattr(task, "due_date", None)
        and getattr(task, "completed_at", None) is None
        and today <= task.due_date <= soon_cutoff
    ]

    return {
        "overdue_tasks": overdue_tasks,
        "due_soon_tasks": due_soon_tasks,
    }