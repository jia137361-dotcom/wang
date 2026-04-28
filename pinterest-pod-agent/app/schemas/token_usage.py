from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TokenUsageRead(BaseModel):
    id: int
    provider: str
    model_name: str
    account_id: str | None = None
    campaign_id: str | None = None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate: float
    request_type: str
    request_id: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TokenUsageSummary(BaseModel):
    record_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_estimate: float
