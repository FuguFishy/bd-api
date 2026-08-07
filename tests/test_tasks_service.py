from datetime import date, timedelta
from types import SimpleNamespace

from app.ui.services.tasks import build_task_page_context


def test_build_task_page_context_groups_tasks():
    today = date.today()
    tasks = [
        SimpleNamespace(id=1, due_date=today - timedelta(days=1), completed_at=None),
        SimpleNamespace(id=2, due_date=today + timedelta(days=3), completed_at=None),
        SimpleNamespace(id=3, due_date=today + timedelta(days=10), completed_at=None),
        SimpleNamespace(id=4, due_date=today + timedelta(days=2), completed_at="done"),
        SimpleNamespace(id=5, due_date=None, completed_at=None),
    ]

    result = build_task_page_context(tasks)

    assert [task.id for task in result["overdue_tasks"]] == [1]
    assert [task.id for task in result["due_soon_tasks"]] == [2]