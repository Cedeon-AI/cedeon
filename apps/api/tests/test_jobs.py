from __future__ import annotations


def test_ping_task_is_registered() -> None:
    from app.jobs import tasks  # noqa: F401  (import registers the task)
    from app.jobs.app import procrastinate_app

    assert "ping" in procrastinate_app.tasks
