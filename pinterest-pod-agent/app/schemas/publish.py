from pathlib import Path

from pydantic import BaseModel, Field


class PublishRequest(BaseModel):
    account_id: str = Field(max_length=64)
    campaign_id: str | None = Field(default=None, max_length=64)
    board_name: str = Field(max_length=160)
    image_path: Path
    title: str = Field(max_length=160)
    description: str
    destination_url: str | None = Field(default=None, max_length=1024)
    product_type: str = Field(max_length=80)
    niche: str = Field(max_length=120)
    audience: str = Field(max_length=240)
    season: str | None = Field(default=None, max_length=80)
    offer: str | None = Field(default=None, max_length=240)
    dry_run: bool = False


class PublishResponse(BaseModel):
    success: bool
    message: str
    pin_url: str | None = None
    pin_performance_id: int | None = None
    content_prompt: str | None = None
    visual_prompt: str | None = None
    strategy_snapshot: dict | None = None
    debug_artifact_dir: str | None = None
