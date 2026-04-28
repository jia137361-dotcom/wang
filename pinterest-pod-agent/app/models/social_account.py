from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SocialAccount(Base):
    __tablename__ = "social_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="pinterest", nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    adspower_profile_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    proxy_region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    risk_status: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
