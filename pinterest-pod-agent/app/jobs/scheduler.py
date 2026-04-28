from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.publish_job import PublishJob


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerSnapshot:
    enabled: bool
    pending_publish_jobs: int
    next_publish_check_at: datetime | None


def scheduler_snapshot(db: Session, *, enabled: bool, interval_minutes: int) -> SchedulerSnapshot:
    pending_count = len(
        db.scalars(select(PublishJob).where(PublishJob.status == "pending")).all()
    )
    return SchedulerSnapshot(
        enabled=enabled,
        pending_publish_jobs=pending_count,
        next_publish_check_at=datetime.now(UTC) + timedelta(minutes=interval_minutes)
        if enabled
        else None,
    )


def mark_next_publish_job_ready(db: Session) -> PublishJob | None:
    job = db.scalar(
        select(PublishJob)
        .where(PublishJob.status == "pending")
        .order_by(PublishJob.created_at.asc())
        .limit(1)
    )
    if job is None:
        return None
    job.status = "ready"
    job.started_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    logger.info("Marked publish job ready", extra={"job_id": job.job_id})
    return job
