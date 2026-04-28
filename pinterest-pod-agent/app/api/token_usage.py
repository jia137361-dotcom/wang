from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.token_usage import TokenUsage
from app.schemas.token_usage import TokenUsageRead, TokenUsageSummary


router = APIRouter()


@router.get("/records", response_model=list[TokenUsageRead])
def list_token_usage(
    provider: str | None = None,
    model_name: str | None = None,
    account_id: str | None = None,
    campaign_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[TokenUsage]:
    stmt = select(TokenUsage).order_by(TokenUsage.created_at.desc()).offset(offset).limit(limit)
    if provider:
        stmt = stmt.where(TokenUsage.provider == provider)
    if model_name:
        stmt = stmt.where(TokenUsage.model_name == model_name)
    if account_id:
        stmt = stmt.where(TokenUsage.account_id == account_id)
    if campaign_id:
        stmt = stmt.where(TokenUsage.campaign_id == campaign_id)
    return list(db.scalars(stmt).all())


@router.get("/summary", response_model=TokenUsageSummary)
def token_usage_summary(
    provider: str | None = None,
    model_name: str | None = None,
    db: Session = Depends(get_db),
) -> TokenUsageSummary:
    stmt = select(TokenUsage)
    if provider:
        stmt = stmt.where(TokenUsage.provider == provider)
    if model_name:
        stmt = stmt.where(TokenUsage.model_name == model_name)
    rows = list(db.scalars(stmt).all())
    return TokenUsageSummary(
        record_count=len(rows),
        prompt_tokens=sum(row.prompt_tokens for row in rows),
        completion_tokens=sum(row.completion_tokens for row in rows),
        total_tokens=sum(row.total_tokens for row in rows),
        cost_estimate=sum(row.cost_estimate for row in rows),
    )
