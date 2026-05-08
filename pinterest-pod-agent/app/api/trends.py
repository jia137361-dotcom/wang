from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.strategy_matrix import get_strategy
from app.jobs.tasks import refresh_current_event_trends_task, refresh_product_trends_task
from app.workflows.trend_scout import get_recorded_trends, record_manual_trends


router = APIRouter()


class TrendKeywordsPayload(BaseModel):
    keywords: list[str] = Field(min_length=1)
    source: str = "manual"


class CurrentEventTrendRefreshPayload(BaseModel):
    query: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ProductTrendRefreshPayload(BaseModel):
    niche: str | None = None
    product_type: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class TrendRefreshResponse(BaseModel):
    task_id: str | None
    task_name: str
    status: str = "queued"


@router.post("/{scope}")
def record_trends(scope: str, payload: TrendKeywordsPayload, db: Session = Depends(get_db)) -> dict:
    return record_manual_trends(db, scope=scope, keywords=payload.keywords, source=payload.source)


@router.get("/{scope}")
def get_trends(scope: str, db: Session = Depends(get_db)) -> dict:
    return {"scope": scope, "keywords": get_recorded_trends(db, scope=scope)}


@router.get("/{scope}/snapshot")
def get_trend_snapshot(scope: str, db: Session = Depends(get_db)) -> dict:
    return {"scope": scope, "strategy": get_strategy(db, scope)}


@router.post("/{scope}/refresh/current-events", response_model=TrendRefreshResponse)
def refresh_current_event_trends(
    scope: str,
    payload: CurrentEventTrendRefreshPayload,
) -> TrendRefreshResponse:
    try:
        result = refresh_current_event_trends_task.delay(scope, payload.query, payload.limit)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return TrendRefreshResponse(
        task_id=getattr(result, "id", None),
        task_name="app.jobs.refresh_current_event_trends",
    )


@router.post("/{scope}/refresh/products", response_model=TrendRefreshResponse)
def refresh_product_trends(
    scope: str,
    payload: ProductTrendRefreshPayload,
) -> TrendRefreshResponse:
    try:
        result = refresh_product_trends_task.delay(
            scope,
            payload.niche,
            payload.product_type,
            payload.limit,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return TrendRefreshResponse(
        task_id=getattr(result, "id", None),
        task_name="app.jobs.refresh_product_trends",
    )
