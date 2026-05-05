from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class PublishJobCreate(BaseModel):
    account_id: str = Field(max_length=64)
    campaign_id: str | None = Field(default=None, max_length=64)
    board_name: str = Field(max_length=160)
    image_path: Path | None = Field(default=None)
    title: str = Field(default="", max_length=160)
    description: str = Field(default="")
    destination_url: str | None = Field(default=None, max_length=1024)
    product_type: str = Field(max_length=80)
    niche: str = Field(max_length=120)
    audience: str = Field(max_length=240)
    season: str | None = Field(default=None, max_length=80)
    offer: str | None = Field(default=None, max_length=240)
    content_hash: str | None = Field(default=None, max_length=64)
    title_hash: str | None = Field(default=None, max_length=64)
    description_hash: str | None = Field(default=None, max_length=64)
    content_batch_id: str | None = Field(default=None, max_length=64)
    variant_angle: str | None = Field(default=None, max_length=160)
    tagged_topics: str | None = None


class ContentGenerateRequest(BaseModel):
    """Request body for generating deduplicated content candidates."""
    product_type: str = Field(max_length=80)
    niche: str = Field(max_length=120)
    audience: str = Field(max_length=240)
    season: str | None = Field(default=None, max_length=80)
    offer: str | None = Field(default=None, max_length=240)
    destination_url: str | None = Field(default=None, max_length=1024)
    account_id: str = Field(max_length=64)


class ContentGenerateResponse(BaseModel):
    title: str
    description: str
    keywords: str = "[]"
    angle: str = ""
    style_variant: str = ""
    title_hash: str = ""
    description_hash: str = ""
    content_hash: str = ""
    content_batch_id: str = ""
    accepted: bool = False
    reason: str = ""


class PublishJobRead(BaseModel):
    id: int
    job_id: str
    account_id: str
    campaign_id: str | None = None
    status: str
    board_name: str
    image_path: str
    title: str
    description: str
    destination_url: str | None = None
    product_type: str
    niche: str
    audience: str
    season: str | None = None
    offer: str | None = None
    error_message: str | None = None
    pin_performance_id: int | None = None
    content_hash: str | None = None
    title_hash: str | None = None
    description_hash: str | None = None
    content_batch_id: str | None = None
    variant_angle: str | None = None
    tagged_topics: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
