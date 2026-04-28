from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PinMetricsUpdate(BaseModel):
    impressions: int = Field(ge=0)
    saves: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    outbound_clicks: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    reactions: int = Field(default=0, ge=0)


class PinPerformanceRead(BaseModel):
    id: int
    account_id: str | None = None
    campaign_id: str | None = None
    pinterest_pin_id: str | None = None
    board_id: str | None = None
    product_type: str | None = None
    niche: str | None = None
    title: str
    description: str
    destination_url: str | None = None
    image_url: str | None = None
    content_prompt: str
    visual_prompt: str | None = None
    model_name: str | None = None
    prompt_version: str
    keywords: list[str]
    strategy_snapshot: dict[str, Any]
    impressions: int
    saves: int
    clicks: int
    outbound_clicks: int
    comments: int
    reactions: int
    ctr: float
    save_rate: float
    engagement_rate: float
    published_at: datetime | None = None
    metrics_updated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AnalyticsSummary(BaseModel):
    pin_count: int
    impressions: int
    clicks: int
    saves: int
    outbound_clicks: int
    comments: int
    reactions: int
    avg_ctr: float
    avg_save_rate: float
    avg_engagement_rate: float
    top_keywords: list[dict[str, int | str]]
