from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SocialAccountBase(BaseModel):
    platform: str = Field(default="pinterest", max_length=40)
    display_name: str | None = Field(default=None, max_length=120)
    adspower_profile_id: str | None = Field(default=None, max_length=120)
    proxy_region: str | None = Field(default=None, max_length=80)
    risk_status: str = Field(default="unknown", max_length=40)


class SocialAccountCreate(SocialAccountBase):
    account_id: str = Field(max_length=64)


class SocialAccountUpdate(BaseModel):
    platform: str | None = Field(default=None, max_length=40)
    display_name: str | None = Field(default=None, max_length=120)
    adspower_profile_id: str | None = Field(default=None, max_length=120)
    proxy_region: str | None = Field(default=None, max_length=80)
    risk_status: str | None = Field(default=None, max_length=40)


class SocialAccountRead(SocialAccountBase):
    id: int
    account_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
