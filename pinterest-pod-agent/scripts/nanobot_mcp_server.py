#!/usr/bin/env python
"""MCP server exposing Pinterest POD Agent operations to nanobot.

Usage (nanobot config.json mcpServers entry):
    {
      "pinterest-pod": {
        "command": ".venv\\Scripts\\python.exe",
        "args": ["scripts\\nanobot_mcp_server.py"],
        "toolTimeout": 60,
        "enabledTools": ["*"]
      }
    }
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# -- ensure project root is on sys.path ---------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger("nanobot_mcp_server")
logging.basicConfig(level=logging.INFO, format="%(levelname)s [mcp] %(message)s")

mcp = FastMCP("pinterest-pod-agent", log_level="INFO")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _db():
    from app.database import get_sessionmaker

    return get_sessionmaker()()


# ---------------------------------------------------------------------------
# 1. create_publish_task
# ---------------------------------------------------------------------------


@mcp.tool()
def create_publish_task(
    account_id: str,
    job_id: str,
    warmup_duration_minutes: int = 5,
    scheduled_at: str | None = None,
    priority: int = 5,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Create a warmup_and_publish scheduled_task for a specific account + job.

    The task will be picked up by the dispatcher at its scheduled time.
    Set dry_run=False for production publishing.
    """
    from uuid import uuid4

    from app.models.publish_job import PublishJob
    from app.models.scheduled_task import ScheduledTask
    from app.models.social_account import SocialAccount

    db = _db()
    try:
        from sqlalchemy import select

        # Validate account exists and has AdsPower profile
        account = db.scalar(
            select(SocialAccount).where(SocialAccount.account_id == account_id)
        )
        if account is None:
            return {"error": f"Account not found: {account_id}"}
        if not account.adspower_profile_id:
            return {"error": f"No AdsPower profile bound for account: {account_id}"}

        # Validate publish_job exists and has image
        job = db.scalar(
            select(PublishJob).where(PublishJob.job_id == job_id)
        )
        if job is None:
            return {"error": f"Publish job not found: {job_id}"}
        # Image will be auto-generated during publish if missing
        if job.status == "cancelled":
            return {"error": f"Publish job is cancelled: {job_id}"}

        now = _now()
        task = ScheduledTask(
            task_id=f"st_{uuid4().hex[:16]}",
            task_type="warmup_and_publish",
            account_id=account_id,
            status="pending",
            priority=priority,
            scheduled_at=datetime.fromisoformat(scheduled_at) if scheduled_at else now,
            payload_json={
                "account_id": account_id,
                "job_id": job_id,
                "warmup_duration_minutes": warmup_duration_minutes,
                "dry_run": dry_run,
            },
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "account_id": task.account_id,
            "status": task.status,
            "scheduled_at": task.scheduled_at.isoformat() if task.scheduled_at else None,
            "dry_run": dry_run,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2. dispatch_ready_tasks
# ---------------------------------------------------------------------------


@mcp.tool()
def dispatch_ready_tasks(
    limit: int = 20,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Manually trigger the task dispatcher NOW (bypasses Beat schedule).

    Directly calls dispatch_ready_tasks() — synchronous, no Celery relay.
    Set dry_run=False for production.  Returns the dispatch summary.
    """
    from app.jobs.dispatcher import dispatch_ready_tasks as _dispatch

    db = _db()
    try:
        result = _dispatch(db, limit=limit, dry_run=dry_run)
        db.commit()
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. get_task_status
# ---------------------------------------------------------------------------


@mcp.tool()
def get_task_status(task_id: str) -> dict[str, Any]:
    """Get detailed info for a single task including payload, result, errors."""
    from app.models.scheduled_task import ScheduledTask

    db = _db()
    try:
        from sqlalchemy import select

        t = db.scalar(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id)
        )
        if t is None:
            return {"error": f"Task not found: {task_id}"}
        return {
            "task_id": t.task_id,
            "task_type": t.task_type,
            "account_id": t.account_id,
            "campaign_id": t.campaign_id,
            "status": t.status,
            "priority": t.priority,
            "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            "attempt_count": t.attempt_count,
            "max_attempts": t.max_attempts,
            "celery_task_id": t.celery_task_id,
            "error_message": t.error_message,
            "error_type": t.error_type,
            "payload": t.payload_json,
            "result": t.result_json,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. get_account_runtime_status
# ---------------------------------------------------------------------------


@mcp.tool()
def get_account_runtime_status() -> dict[str, Any]:
    """Today's overview: per-account completed/running/pending/failed counts."""
    from app.models.scheduled_task import ScheduledTask

    db = _db()
    try:
        from sqlalchemy import func, select

        today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = list(
            db.execute(
                select(
                    ScheduledTask.account_id,
                    ScheduledTask.status,
                    func.count(ScheduledTask.id),
                )
                .where(
                    (ScheduledTask.scheduled_at >= today)
                    | (ScheduledTask.status.in_(["running"]))
                )
                .group_by(ScheduledTask.account_id, ScheduledTask.status)
            ).all()
        )

        by_account: dict[str, dict[str, int]] = {}
        for row in rows:
            aid = row.account_id or "(no account)"
            if aid not in by_account:
                by_account[aid] = {}
            by_account[aid][row.status] = row.count

        return {
            "date": today.date().isoformat(),
            "accounts": {
                aid: {
                    "completed": counts.get("completed", 0),
                    "running": counts.get("running", 0),
                    "pending": counts.get("pending", 0),
                    "failed": counts.get("failed", 0),
                    "total": (
                        counts.get("completed", 0)
                        + counts.get("running", 0)
                        + counts.get("pending", 0)
                        + counts.get("failed", 0)
                    ),
                }
                for aid, counts in by_account.items()
            },
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. store_trend_signals
# ---------------------------------------------------------------------------


@mcp.tool()
def store_trend_signals(
    scope: str,
    bucket: str,
    signals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Store trend keywords collected by nanobot into the global_strategy table.

    *scope*: typically an account_id or niche name
    *bucket*: "current_event_trends" or "product_trends"
    *signals*: list of {keyword, weight, source, metadata?}

    These keywords are then consumed by EvoMap prompt generation.
    """
    from app.evomap.strategy_matrix import get_strategy, upsert_strategy

    db = _db()
    try:
        strategy = get_strategy(db, scope)
        normalized = [
            {
                "keyword": " ".join(s.get("keyword", "").lower().split()),
                "source": s.get("source", "nanobot"),
                "weight": s.get("weight", 1.0),
                "metadata": s.get("metadata", {}),
            }
            for s in signals
            if s.get("keyword", "").strip()
        ]
        if not normalized:
            return {"stored": 0, "message": "No valid keyword signals provided"}

        strategy[bucket] = normalized
        strategy["trend_keywords"] = sorted(
            {item["keyword"] for item in normalized}
        )

        history = strategy.get("trend_history", [])
        history.append(
            {
                "source": bucket,
                "count": len(normalized),
                "recorded_at": _now().isoformat(),
            }
        )
        strategy["trend_history"] = history[-50:]
        short_bucket = {"current_event_trends": "cet", "product_trends": "pt"}.get(
            bucket, bucket[:8]
        )
        strategy["version"] = f"nb_{short_bucket}_{_now().strftime('%Y%m%d%H%M')}"

        upsert_strategy(db, scope, strategy, version=strategy["version"])
        db.commit()

        return {
            "stored": len(normalized),
            "bucket": bucket,
            "scope": scope,
            "keywords": strategy["trend_keywords"],
            "version": strategy["version"],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6. publish_pin_direct (forced dry_run=True)
# ---------------------------------------------------------------------------


@mcp.tool()
def publish_pin_direct(
    account_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Publish a Pin immediately via warmup_and_publish (dry-run only).

    This tool always runs in dry_run mode — no real Pinterest publishing.
    Use create_publish_task + dispatch_ready_tasks for production.
    """
    from app.models.publish_job import PublishJob
    from app.models.social_account import SocialAccount

    db = _db()
    try:
        from sqlalchemy import select

        account = db.scalar(
            select(SocialAccount).where(SocialAccount.account_id == account_id)
        )
        if account is None:
            return {"error": f"Account not found: {account_id}"}
        if not account.adspower_profile_id:
            return {"error": f"No AdsPower profile bound for account: {account_id}"}

        job = db.scalar(
            select(PublishJob).where(PublishJob.job_id == job_id)
        )
        if job is None:
            return {"error": f"Publish job not found: {job_id}"}
        # Image will be auto-generated during publish if missing
        if job.status == "cancelled":
            return {"error": f"Publish job is cancelled: {job_id}"}
    finally:
        db.close()

    from app.jobs.tasks import warmup_and_publish_task

    result = warmup_and_publish_task.delay(
        account_id=account_id,
        job_id=job_id,
        warmup_duration_minutes=0,
        dry_run=True,
    )
    return {
        "celery_task_id": result.id,
        "job_id": job_id,
        "account_id": account_id,
        "dry_run": True,
        "note": "Check task status with get_task_status",
    }


# ---------------------------------------------------------------------------
# 7. auto_schedule_daily
# ---------------------------------------------------------------------------


@mcp.tool()
def auto_schedule_daily(
    account_ids: list[str] | None = None,
    dry_run: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Generate today's task schedule: warmup_and_publish for each account.

    Only creates warmup_and_publish tasks when ready publish_jobs exist.
    Does NOT fall back to standalone warmup — time slots without ready jobs
    are simply skipped.  Pass force=True to override idempotency check.
    """
    from uuid import uuid4

    from app.models.account_policy import AccountPolicy
    from app.models.scheduled_task import ScheduledTask
    from app.models.social_account import SocialAccount

    db = _db()
    try:
        from sqlalchemy import func, select

        stmt = select(SocialAccount)
        if account_ids:
            stmt = stmt.where(SocialAccount.account_id.in_(account_ids))
        accounts = list(db.scalars(stmt).all())

        if not accounts:
            return {"scheduled": 0, "message": "No accounts found", "accounts": []}

        now = _now()
        base_hour = now.hour + 1

        summary: list[dict[str, Any]] = []
        scheduled_count = 0

        # idempotency check (skipped when force=True)
        if not force:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            existing_task_count = db.scalar(
                select(func.count(ScheduledTask.id)).where(
                    ScheduledTask.scheduled_at >= today_start,
                    ScheduledTask.scheduled_at < today_start + timedelta(days=1),
                    ScheduledTask.status.in_(["pending", "ready", "scheduled"]),
                )
            ) or 0
            if existing_task_count > 0:
                return {
                    "scheduled": 0,
                    "message": f"Tasks already scheduled for today ({existing_task_count} pending). Use force=True to override.",
                    "accounts": [],
                }

        for idx, account in enumerate(accounts):
            policy = db.scalar(
                select(AccountPolicy).where(
                    AccountPolicy.account_id == account.account_id
                )
            )
            daily_posts = policy.daily_max_posts if policy else 2
            warmup_sessions = policy.warmup_sessions_per_day if policy else 2
            warmup_duration = policy.warmup_duration_min if policy else 5

            acc_summary: dict[str, Any] = {
                "account_id": account.account_id,
                "tasks": [],
            }

            offset_h = idx * 2

            from app.models.publish_job import PublishJob

            ready_jobs = list(
                db.scalars(
                    select(PublishJob)
                    .where(
                        PublishJob.account_id == account.account_id,
                        PublishJob.status.in_(["pending", "ready"]),
                    )
                    .order_by(PublishJob.created_at.asc())
                ).all()
            )

            for s in range(min(warmup_sessions, daily_posts)):
                scheduled_hour = (base_hour + offset_h + s * 4) % 24
                scheduled_at = now.replace(
                    hour=scheduled_hour, minute=30, second=0, microsecond=0
                )
                if scheduled_at <= now:
                    continue

                if not ready_jobs:
                    # No ready publish_job — skip this time slot
                    continue

                publish_job = ready_jobs.pop(0)
                task_id = f"st_{uuid4().hex[:16]}"
                payload = {
                    "account_id": account.account_id,
                    "warmup_duration_minutes": warmup_duration,
                    "job_id": publish_job.job_id,
                }
                task = ScheduledTask(
                    task_id=task_id,
                    task_type="warmup_and_publish",
                    account_id=account.account_id,
                    status="pending",
                    priority=5,
                    scheduled_at=scheduled_at,
                    payload_json=payload,
                )
                db.add(task)
                scheduled_count += 1
                acc_summary["tasks"].append(
                    {
                        "task_id": task_id,
                        "type": "warmup_and_publish",
                        "scheduled_at": scheduled_at.isoformat(),
                        "warmup_min": warmup_duration,
                        "job_id": publish_job.job_id,
                    }
                )

            # auto-reply: one pass per day in the evening
            if policy and policy.auto_reply_enabled:
                reply_hour = (base_hour + offset_h + 8) % 24
                reply_at = now.replace(
                    hour=reply_hour, minute=0, second=0, microsecond=0
                )
                if reply_at > now:
                    task_id = f"st_{uuid4().hex[:16]}"
                    task = ScheduledTask(
                        task_id=task_id,
                        task_type="auto_reply",
                        account_id=account.account_id,
                        status="pending",
                        priority=3,
                        scheduled_at=reply_at,
                        payload_json={
                            "account_id": account.account_id,
                            "dry_run": dry_run,
                            "limit": 20,
                        },
                    )
                    db.add(task)
                    scheduled_count += 1
                    acc_summary["tasks"].append(
                        {
                            "task_id": task_id,
                            "type": "auto_reply",
                            "scheduled_at": reply_at.isoformat(),
                        }
                    )

            db.commit()
            summary.append(acc_summary)

        return {
            "scheduled": scheduled_count,
            "dry_run": dry_run,
            "accounts": summary,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
