from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrategyUpsert(BaseModel):
    strategy: dict[str, Any] = Field(default_factory=dict)
    version: str = Field(default="v1", max_length=40)


class StrategyRead(BaseModel):
    id: int
    scope: str
    strategy: dict[str, Any]
    version: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
