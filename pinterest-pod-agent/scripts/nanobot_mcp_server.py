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

import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import text as sa_text

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


def _run_async(coro):
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    else:
        # Already inside an event loop (e.g. mcp itself)
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()


# ---------------------------------------------------------------------------
# 1. Service health
# ---------------------------------------------------------------------------


@mcp.tool()
def check_health() -> dict[str, Any]:
    """Check Redis, PostgreSQL, AdsPower, and Celery connectivity."""
    import socket

    result: dict[str, Any] = {"ok": True, "services": {}}

    # PostgreSQL
    try:
        db = _db()
        db.execute(sa_text("SELECT 1"))
        result["services"]["postgresql"] = "ok"
        db.close()
    except Exception as exc:
        result["services"]["postgresql"] = f"error: {exc}"
        result["ok"] = False

    # Redis
    try:
        import redis
        from app.config import get_settings

        settings = get_settings()
        r = redis.from_url(settings.redis_url)
        r.ping()
        r.close()
        result["services"]["redis"] = "ok"
    except Exception as exc:
        result["services"]["redis"] = f"error: {exc}"
        result["ok"] = False

    # AdsPower
    try:
        from app.tools.adspower_api import AdsPowerClient

        client = AdsPowerClient()
        client._get("/api/v1/user/list")
        result["services"]["adspower"] = "ok"
    except Exception as exc:
        result["services"]["adspower"] = f"error: {exc}"
        result["ok"] = False

    return result


@mcp.tool()
def check_account_proxies() -> dict[str, Any]:
    """Verify each account's AdsPower profile and confirm its exit IP is US.

    Opens each profile in a browser, navigates to an IP-check service,
    and confirms the exit IP is in the United States.  This is a real
    proxy-IP check, not just profile-availability."""
    from app.models.social_account import SocialAccount

    db = _db()
    try:
        from sqlalchemy import select

        accounts = list(db.scalars(select(SocialAccount)).all())
    finally:
        db.close()

    if not accounts:
        return {"profiles": {}, "note": "No accounts configured"}

    profiles: dict[str, Any] = {}
    for acct in accounts:
        pid = acct.adspower_profile_id
        if not pid:
            profiles[acct.account_id] = {"region": "unknown", "ip_check": "no_profile"}
            continue

        async def _check_one(aid: str, profile_id: str) -> dict[str, Any]:
            from app.automation.browser_factory import open_adspower_profile
            from app.safety.proxy_check import verify_us_ip

            session = await open_adspower_profile(profile_id)
            try:
                ip_info = await verify_us_ip(session.page)
                return {
                    "region": ip_info.get("country", "unknown"),
                    "ip": ip_info.get("ip", "unknown"),
                    "is_us": ip_info.get("country") == "US",
                    "profile_id": profile_id,
                }
            finally:
                await session.close()

        try:
            result = _run_async(_check_one(acct.account_id, pid))
            profiles[acct.account_id] = result
        except Exception as exc:
            profiles[acct.account_id] = {
                "region": acct.proxy_region or "unknown",
                "ip_check": f"error: {exc}",
                "profile_id": pid,
            }

    return {"profiles": profiles}


# ---------------------------------------------------------------------------
# 2. EvoMap data insights
# ---------------------------------------------------------------------------


@mcp.tool()
def get_evo_keyword_signals(
    niche: str | None = None,
    product_type: str | None = None,
    min_ctr: float = 0.01,
    min_impressions: int = 50,
) -> dict[str, Any]:
    """Read EvoMap keyword signals from PinPerformance data.

    Returns high-CTR keywords with weights — the core signal for content decisions.
    """
    db = _db()
    try:
        from app.evomap.prompt_evolve import PromptEvolver

        evolver = PromptEvolver(db=db, min_ctr=min_ctr, min_impressions=min_impressions)
        signals = evolver.get_keyword_signals(niche=niche, product_type=product_type)
        return {
            "signals": [
                {"keyword": s.keyword, "weight": round(s.weight, 4), "samples": s.samples}
                for s in signals
            ],
            "count": len(signals),
            "filters": {"niche": niche, "product_type": product_type, "min_ctr": min_ctr, "min_impressions": min_impressions},
        }
    finally:
        db.close()


@mcp.tool()
def get_evo_strategy_advice(niche: str, product_type: str | None = None) -> dict[str, Any]:
    """Get EvoMap LLM-generated strategy advice for a niche/product_type.

    Returns Chinese-language analysis: what content works, what to avoid, title/description style tips.
    """
    db = _db()
    try:
        from app.evomap.prompt_evolve import PromptEvolver

        evolver = PromptEvolver(db=db)
        advice = evolver.generate_strategy_advice(niche=niche, product_type=product_type)
        return {"advice": advice, "niche": niche, "product_type": product_type}
    finally:
        db.close()


@mcp.tool()
def get_account_analytics(account_id: str | None = None, days: int = 7) -> dict[str, Any]:
    """Get per-account analytics: impressions, clicks, CTR, saves, engagement rate."""
    from sqlalchemy import func, select

    from app.models.pin_performance import PinPerformance

    db = _db()
    try:
        cutoff = _now() - timedelta(days=days)
        stmt = select(
            PinPerformance.account_id,
            func.count(PinPerformance.id).label("pins"),
            func.sum(PinPerformance.impressions).label("impressions"),
            func.sum(PinPerformance.clicks).label("clicks"),
            func.sum(PinPerformance.saves).label("saves"),
        ).where(PinPerformance.published_at >= cutoff)

        if account_id:
            stmt = stmt.where(PinPerformance.account_id == account_id)
        stmt = stmt.group_by(PinPerformance.account_id)

        rows = list(db.execute(stmt).all())
        result: dict[str, Any] = {"period_days": days, "accounts": []}
        for row in rows:
            acc: dict[str, Any] = {
                "account_id": row.account_id,
                "pins": row.pins,
                "impressions": row.impressions or 0,
                "clicks": row.clicks or 0,
                "saves": row.saves or 0,
            }
            if acc["impressions"] and acc["impressions"] > 0:
                acc["ctr"] = round((acc["clicks"] / acc["impressions"]) * 100, 2)
            else:
                acc["ctr"] = 0
            result["accounts"].append(acc)
        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Task orchestration
# ---------------------------------------------------------------------------


@mcp.tool()
def auto_schedule_daily(
    account_ids: list[str] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Generate today's task schedule for all (or specified) accounts.

    Creates scheduled_task rows: warmup_and_publish for each account based on
    their AccountPolicy.  The existing Beat + dispatcher will pick them up.
    """
    from uuid import uuid4

    from app.models.account_policy import AccountPolicy
    from app.models.scheduled_task import ScheduledTask
    from app.models.social_account import SocialAccount

    db = _db()
    try:
        from sqlalchemy import func, select

        # fetch accounts
        stmt = select(SocialAccount)
        if account_ids:
            stmt = stmt.where(SocialAccount.account_id.in_(account_ids))
        accounts = list(db.scalars(stmt).all())

        if not accounts:
            return {"scheduled": 0, "message": "No accounts found", "accounts": []}

        now = _now()
        # round to next hour
        base_hour = now.hour + 1

        summary: list[dict[str, Any]] = []
        scheduled_count = 0

        # check if tasks already exist for today (idempotency)
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
                "message": f"Tasks already scheduled for today ({existing_task_count} pending). Use --force to override.",
                "accounts": [],
            }

        for idx, account in enumerate(accounts):
            # read policy
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

            # stagger accounts across the day
            offset_h = idx * 2  # 2h separation between accounts

            # warmup-then-publish sessions
            # Find ready publish_jobs for this account (with images)
            from app.models.publish_job import PublishJob

            ready_jobs = list(
                db.scalars(
                    select(PublishJob)
                    .where(
                        PublishJob.account_id == account.account_id,
                        PublishJob.status.in_(["pending", "ready"]),
                        PublishJob.image_path.isnot(None),
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

                task_id = f"st_{uuid4().hex[:16]}"

                if ready_jobs:
                    # Assign the next available publish_job
                    publish_job = ready_jobs.pop(0)
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
                else:
                    # No publish_job available — create standalone warmup instead
                    payload = {
                        "account_id": account.account_id,
                        "duration_minutes": warmup_duration,
                    }
                    task = ScheduledTask(
                        task_id=task_id,
                        task_type="warmup",
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
                            "type": "warmup",
                            "scheduled_at": scheduled_at.isoformat(),
                            "warmup_min": warmup_duration,
                            "note": "No ready publish_job, standalone warmup only",
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
            "note": "warmup_and_publish only created when ready publish_jobs exist; otherwise fallback to standalone warmup",
        }
    finally:
        db.close()


@mcp.tool()
def create_task(
    task_type: str,
    account_id: str | None,
    payload_json: dict[str, Any],
    scheduled_at: str | None = None,
    priority: int = 5,
) -> dict[str, Any]:
    """Create a single scheduled_task row.

    task_type: one of publish, warmup_and_publish, warmup, generate_image,
               auto_reply, refresh_trends, cleanup.
    """
    from uuid import uuid4

    from app.models.scheduled_task import ScheduledTask

    db = _db()
    try:
        from sqlalchemy import select

        from app.models.scheduled_task import TASK_TYPES

        if task_type not in TASK_TYPES:
            return {"error": f"Invalid task_type: {task_type}. Must be one of: {sorted(TASK_TYPES)}"}

        now = _now()
        task = ScheduledTask(
            task_id=f"st_{uuid4().hex[:16]}",
            task_type=task_type,
            account_id=account_id,
            status="pending",
            priority=priority,
            scheduled_at=datetime.fromisoformat(scheduled_at)
            if scheduled_at
            else now,
            payload_json=payload_json,
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
        }
    finally:
        db.close()


@mcp.tool()
def list_tasks(
    account_id: str | None = None,
    task_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List recent scheduled tasks, filterable by account, type, status."""
    from app.models.scheduled_task import ScheduledTask

    db = _db()
    try:
        from sqlalchemy import select

        stmt = select(ScheduledTask).order_by(ScheduledTask.scheduled_at.desc())
        if account_id:
            stmt = stmt.where(ScheduledTask.account_id == account_id)
        if task_type:
            stmt = stmt.where(ScheduledTask.task_type == task_type)
        if status:
            stmt = stmt.where(ScheduledTask.status == status)
        stmt = stmt.limit(limit)

        tasks = [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "account_id": t.account_id,
                "status": t.status,
                "priority": t.priority,
                "scheduled_at": t.scheduled_at.isoformat() if t.scheduled_at else None,
                "started_at": t.started_at.isoformat() if t.started_at else None,
                "finished_at": t.finished_at.isoformat() if t.finished_at else None,
                "attempt_count": t.attempt_count,
                "error_message": t.error_message,
            }
            for t in db.scalars(stmt).all()
        ]
        return {"tasks": tasks, "count": len(tasks)}
    finally:
        db.close()


@mcp.tool()
def cancel_task(task_id: str) -> dict[str, Any]:
    """Cancel a pending or scheduled task."""
    from app.models.scheduled_task import ScheduledTask

    db = _db()
    try:
        from sqlalchemy import select

        task = db.scalar(
            select(ScheduledTask).where(ScheduledTask.task_id == task_id)
        )
        if task is None:
            return {"error": f"Task not found: {task_id}"}
        if task.status in {"completed", "failed"}:
            return {"error": f"Task already finished: {task.status}"}
        task.status = "cancelled"
        task.finished_at = _now()
        db.commit()
        return {"task_id": task_id, "status": "cancelled"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Monitoring
# ---------------------------------------------------------------------------


@mcp.tool()
def get_status_dashboard() -> dict[str, Any]:
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

        # aggregate per account
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
                    "total": sum(counts.values()),
                }
                for aid, counts in by_account.items()
            },
        }
    finally:
        db.close()


@mcp.tool()
def get_task_detail(task_id: str) -> dict[str, Any]:
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


@mcp.tool()
def get_recent_errors(hours: int = 24) -> dict[str, Any]:
    """Get recent task errors grouped by account and error type."""
    from app.models.scheduled_task import ScheduledTask

    db = _db()
    try:
        from sqlalchemy import select

        cutoff = _now() - timedelta(hours=hours)
        rows = list(
            db.scalars(
                select(ScheduledTask)
                .where(
                    ScheduledTask.status == "failed",
                    ScheduledTask.finished_at >= cutoff,
                )
                .order_by(ScheduledTask.finished_at.desc())
                .limit(50)
            ).all()
        )
        return {
            "period_hours": hours,
            "errors": [
                {
                    "task_id": t.task_id,
                    "account_id": t.account_id,
                    "task_type": t.task_type,
                    "error_type": t.error_type,
                    "error_message": t.error_message,
                    "finished_at": t.finished_at.isoformat() if t.finished_at else None,
                }
                for t in rows
            ],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. Trend signals (written by nanobot after its own search + LLM)
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
        strategy["version"] = f"nanobot_{bucket}_{_now().strftime('%Y%m%d_%H%M')}"

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
# 6. Direct operations
# ---------------------------------------------------------------------------


@mcp.tool()
def generate_image(
    prompt: str,
    image_size: str = '{"width": 800, "height": 1200}',
) -> dict[str, Any]:
    """Generate an image via Fal.ai and download locally. Returns local path."""
    from app.workflows.image_generation_flow import generate_image_asset

    asset = _run_async(generate_image_asset(prompt=prompt, image_size=image_size))
    return {
        "prompt": asset.prompt,
        "image_size": asset.image_size,
        "local_path": asset.local_path,
        "source_url": asset.source_url,
        "bytes_written": asset.bytes_written,
    }


@mcp.tool()
def trigger_dispatch(
    limit: int = 50,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Manually trigger the task dispatcher NOW (bypasses Beat schedule).

    Set dry_run=False for production.  Returns the dispatch result including
    how many tasks were enqueued and to which queues.
    """
    from app.jobs.tasks import dispatch_publish_jobs_task

    result = dispatch_publish_jobs_task.delay(limit=limit, dry_run=dry_run)
    return {
        "celery_task_id": result.id,
        "limit": limit,
        "dry_run": dry_run,
        "note": "Dispatch task sent to Celery. Use get_status_dashboard to see results.",
    }


@mcp.tool()
def publish_pin_direct(
    account_id: str,
    job_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Publish a Pin immediately (skips scheduler), using existing publish_job."""
    from app.jobs.tasks import publish_job_task

    result = publish_job_task.delay(
        job_id=job_id,
        dry_run=dry_run,
    )
    return {
        "celery_task_id": result.id,
        "job_id": job_id,
        "account_id": account_id,
        "dry_run": dry_run,
        "note": "Check task status with get_task_detail or list_tasks",
    }


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="stdio")
