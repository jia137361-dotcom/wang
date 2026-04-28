from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from app.config import get_settings


F = TypeVar("F", bound=Callable[..., Any])


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Safely run an async coroutine from a synchronous Celery task.

    Uses a fresh event loop per call so it works with every Celery pool
    (solo, prefork, eventlet, gevent).
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

try:
    from celery import Celery
except ImportError:  # pragma: no cover - keeps FastAPI importable before deps are installed.
    Celery = None  # type: ignore[assignment]


class MissingCeleryApp:
    """Small compatibility shim used until celery is installed."""

    def task(self, *decorator_args: Any, **decorator_kwargs: Any) -> Callable[[F], F] | F:
        if decorator_args and callable(decorator_args[0]) and not decorator_kwargs:
            return self._wrap_task(decorator_args[0])

        def decorator(func: F) -> F:
            return self._wrap_task(func)

        return decorator

    def _wrap_task(self, func: F) -> F:
        def missing_delay(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Celery is not installed. Install celery[redis] and start a worker.")

        setattr(func, "delay", missing_delay)
        setattr(func, "apply_async", missing_delay)
        return func


settings = get_settings()

if Celery is None:
    celery_app: Any = MissingCeleryApp()
else:
    celery_app = Celery(
        "pinterest_pod_agent",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.jobs.tasks"],
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone=settings.scheduler_timezone,
        enable_utc=True,
        task_track_started=True,
        beat_schedule={
            "dispatch-publish-jobs": {
                "task": "app.jobs.dispatch_publish_jobs",
                "schedule": settings.publish_interval_minutes * 60,
                "kwargs": {"dry_run": settings.scheduler_dry_run},
            }
        }
        if settings.scheduler_enabled
        else {},
    )
