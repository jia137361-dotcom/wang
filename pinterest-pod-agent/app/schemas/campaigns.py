from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CampaignBase(BaseModel):
    name: str = Field(max_length=160)
    niche: str | None = Field(default=None, max_length=120)
    product_type: str | None = Field(default=None, max_length=80)
    audience: str | None = Field(default=None, max_length=240)
    season: str | None = Field(default=None, max_length=80)
    offer: str | None = Field(default=None, max_length=240)
    destination_url: str | None = Field(default=None, max_length=1024)
    status: str = Field(default="draft", max_length=40)
    start_at: datetime | None = None
    end_at: datetime | None = None


class CampaignCreate(CampaignBase):
    campaign_id: str = Field(max_length=64)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    niche: str | None = Field(default=None, max_length=120)
    product_type: str | None = Field(default=None, max_length=80)
    audience: str | None = Field(default=None, max_length=240)
    season: str | None = Field(default=None, max_length=80)
    offer: str | None = Field(default=None, max_length=240)
    destination_url: str | None = Field(default=None, max_length=1024)
    status: str | None = Field(default=None, max_length=40)
    start_at: datetime | None = None
    end_at: datetime | None = None


class CampaignRead(CampaignBase):
    id: int
    campaign_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
