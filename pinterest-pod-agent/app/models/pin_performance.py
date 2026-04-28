from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PinPerformance(Base):
    """Posting record plus downstream Pinterest feedback.

    EvoMap links generated prompts, strategy snapshots, and resulting metrics
    in one table so future prompt builders can learn from high-performing Pins.
    """

    __tablename__ = "pin_performance"
    __table_args__ = (
        Index("ix_pin_performance_account_published", "account_id", "published_at"),
        Index("ix_pin_performance_niche_product", "niche", "product_type"),
        Index("ix_pin_performance_pinterest_pin_id", "pinterest_pin_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    account_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    campaign_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    pinterest_pin_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    board_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    product_type: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    niche: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    destination_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    content_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    visual_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(40), default="v1", nullable=False)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    strategy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    saves: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outbound_clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    save_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    title_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    description_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    content_batch_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    variant_angle: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @hybrid_property
    def feedback_score(self) -> float:
        return self.ctr * 0.5 + self.save_rate * 0.3 + self.engagement_rate * 0.2

    def refresh_rates(self) -> None:
        if self.impressions <= 0:
            self.ctr = 0.0
            self.save_rate = 0.0
            self.engagement_rate = 0.0
            return

        self.ctr = self.clicks / self.impressions
        self.save_rate = self.saves / self.impressions
        self.engagement_rate = (self.saves + self.comments + self.reactions) / self.impressions

    def to_summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pinterest_pin_id": self.pinterest_pin_id,
            "title": self.title,
            "niche": self.niche,
            "product_type": self.product_type,
            "keywords": self.keywords,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "saves": self.saves,
            "ctr": self.ctr,
            "save_rate": self.save_rate,
            "engagement_rate": self.engagement_rate,
            "feedback_score": self.feedback_score,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "content_hash": self.content_hash,
            "title_hash": self.title_hash,
            "content_batch_id": self.content_batch_id,
            "variant_angle": self.variant_angle,
        }
