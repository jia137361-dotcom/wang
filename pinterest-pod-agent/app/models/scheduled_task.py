"""Unified scheduled task model --- the single entry point for all async work.

Every piece of work (publish, generate_image, generate_video, auto_reply,
refresh_trends, warmup, cleanup) is represented as a ScheduledTask row.
The dispatcher scans this table and enqueues Celery tasks accordingly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


TASK_TYPES = frozenset(
    {
        "publish",
        "generate_image",
        "generate_video",
        "auto_reply",
        "refresh_trends",
        "warmup",
        "warmup_and_publish",
        "cleanup",
        "reclaim_stale",
    }
)


class ScheduledTask(Base):
    __tablename__ = "scheduled_task"
    __table_args__ = (
        Index("ix_st_status_scheduled", "status", "scheduled_at"),
        Index("ix_st_account_status", "account_id", "status"),
        Index("ix_st_locked_by", "locked_by"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    task_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="pinterest", nullable=False)

    account_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    status: Mapped[str] = mapped_column(
        String(40), default="pending", index=True, nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lock_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    celery_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
