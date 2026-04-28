from sqlalchemy.orm import Session

from app.models.token_usage import TokenUsage


class TokenLimiter:
    def __init__(self, daily_budget_tokens: int) -> None:
        self.daily_budget_tokens = daily_budget_tokens
        self.used_tokens = 0

    def can_consume(self, tokens: int) -> bool:
        return self.used_tokens + tokens <= self.daily_budget_tokens

    def consume(self, tokens: int) -> None:
        if not self.can_consume(tokens):
            raise RuntimeError("Daily token budget exceeded")
        self.used_tokens += tokens


def record_token_usage(
    db: Session,
    *,
    model_name: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    provider: str = "volcengine",
    account_id: str | None = None,
    campaign_id: str | None = None,
    request_type: str = "chat",
    request_id: str | None = None,
    cost_estimate: float = 0.0,
) -> TokenUsage:
    record = TokenUsage(
        provider=provider,
        model_name=model_name,
        account_id=account_id,
        campaign_id=campaign_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens or prompt_tokens + completion_tokens,
        cost_estimate=cost_estimate,
        request_type=request_type,
        request_id=request_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
