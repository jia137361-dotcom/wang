from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReplyRecord(Base):
    __tablename__ = "reply_record"
    __table_args__ = (
        UniqueConstraint("account_id", "comment_id", name="ux_reply_record_account_comment"),
        Index("ix_reply_record_account_status", "account_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    comment_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    pin_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="suggested", index=True, nullable=False)
    safety_status: Mapped[str] = mapped_column(String(40), default="safe", nullable=False)
    safety_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
