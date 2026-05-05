from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PublishJob(Base):
    __tablename__ = "publish_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True, nullable=False)
    board_name: Mapped[str] = mapped_column(String(160), nullable=False)
    image_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    destination_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    product_type: Mapped[str] = mapped_column(String(80), nullable=False)
    niche: Mapped[str] = mapped_column(String(120), nullable=False)
    audience: Mapped[str] = mapped_column(String(240), nullable=False)
    season: Mapped[str | None] = mapped_column(String(80), nullable=True)
    offer: Mapped[str | None] = mapped_column(String(240), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_performance_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    title_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    description_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    content_batch_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    variant_angle: Mapped[str | None] = mapped_column(String(160), nullable=True)
    tagged_topics: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
