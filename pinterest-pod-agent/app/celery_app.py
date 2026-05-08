from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from app.config import get_settings


F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger(__name__)


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


def _build_beat_schedule() -> dict[str, dict[str, Any]]:
    if not settings.scheduler_enabled:
        return {}

    schedule: dict[str, dict[str, Any]] = {
        "reclaim-stale-tasks": {
            "task": "app.jobs.reclaim_stale_tasks",
            "schedule": 600,
            "kwargs": {"stale_minutes": 45},
            "options": {"queue": "trend"},
        },
    }
    if settings.scheduler_auto_dispatch_enabled:
        schedule["dispatch-publish-jobs"] = {
            "task": "app.jobs.dispatch_publish_jobs",
            "schedule": settings.publish_interval_minutes * 60,
            "kwargs": {"dry_run": settings.scheduler_dry_run},
            "options": {"queue": "publish"},
        }
    return schedule

TASK_TIME_LIMITS = {
    "app.jobs.publish_job":              {"soft_time_limit": 600,  "time_limit": 900},
    "app.jobs.generate_image_asset":     {"soft_time_limit": 240,  "time_limit": 300},
    "app.jobs.generate_image_for_publish_job": {"soft_time_limit": 240, "time_limit": 300},
    "app.jobs.generate_marketing_video": {"soft_time_limit": 1800, "time_limit": 2400},
    "app.jobs.auto_reply":               {"soft_time_limit": 300,  "time_limit": 600},
    "app.jobs.refresh_current_event_trends": {"soft_time_limit": 180, "time_limit": 300},
    "app.jobs.refresh_product_trends":   {"soft_time_limit": 180,  "time_limit": 300},
    "app.jobs.dispatch_publish_jobs":    {"soft_time_limit": 60,   "time_limit": 120},
    "app.jobs.cleanup_assets":           {"soft_time_limit": 120,  "time_limit": 300},
    "app.jobs.warmup":                   {"soft_time_limit": 1800, "time_limit": 2400},
    "app.jobs.warmup_and_publish":       {"soft_time_limit": 1800, "time_limit": 2400},
    "app.jobs.reclaim_stale_tasks":      {"soft_time_limit": 60,   "time_limit": 120},
}

TASK_QUEUE_ROUTES = {
    "app.jobs.publish_job":              "publish",
    "app.jobs.generate_image_asset":     "media",
    "app.jobs.generate_image_for_publish_job": "media",
    "app.jobs.generate_marketing_video": "media",
    "app.jobs.auto_reply":               "engagement",
    "app.jobs.refresh_current_event_trends": "trend",
    "app.jobs.refresh_product_trends":   "trend",
    "app.jobs.dispatch_publish_jobs":    "publish",
    "app.jobs.cleanup_assets":           "trend",
    "app.jobs.warmup":                   "publish",
    "app.jobs.warmup_and_publish":       "publish",
    "app.jobs.reclaim_stale_tasks":      "trend",
}

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
        task_soft_time_limit=600,
        task_time_limit=900,
        task_annotations=TASK_TIME_LIMITS,
        task_routes=TASK_QUEUE_ROUTES,
        task_create_missing_queues=True,
        worker_max_tasks_per_child=20,
        worker_prefetch_multiplier=1,
        beat_schedule=_build_beat_schedule(),
    )

    try:
        from celery.signals import worker_shutdown

        @worker_shutdown.connect
        def _on_worker_shutdown(**kwargs: Any) -> None:
            """Gracefully close any orphaned browser sessions on worker exit."""
            logger.info("Celery worker shutting down — cleaning up browser sessions")
            # Release any held Redis locks and close connections
            try:
                from app.safety.locks import _get_redis, _get_redis_sync
                import asyncio
                async def _close_async() -> None:
                    r = await _get_redis()
                    await r.aclose()
                asyncio.get_event_loop().run_until_complete(_close_async())
            except Exception:
                pass
            try:
                _get_redis_sync().close()
            except Exception:
                pass
    except ImportError:
        pass
