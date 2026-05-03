"""Per-account rate-limiting and scheduling policy.

Each account can have a policy that controls how often it can publish,
when warmup sessions run, and whether auto-reply is enabled.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccountPolicy(Base):
    __tablename__ = "account_policy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="pinterest", nullable=False)

    daily_max_posts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    min_post_interval_min: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    allowed_timezone_start: Mapped[str | None] = mapped_column(String(5), default="09:00", nullable=True)
    allowed_timezone_end: Mapped[str | None] = mapped_column(String(5), default="22:00", nullable=True)

    auto_reply_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    warmup_sessions_per_day: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    warmup_duration_min: Mapped[int] = mapped_column(Integer, default=15, nullable=False)

    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
