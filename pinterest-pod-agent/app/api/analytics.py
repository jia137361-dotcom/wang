from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.feedback_loop import update_pin_metrics
from app.models.pin_performance import PinPerformance
from app.schemas.analytics import AnalyticsSummary, PinMetricsUpdate, PinPerformanceRead


router = APIRouter()


@router.get("/pins", response_model=list[PinPerformanceRead])
def list_pin_performance(
    account_id: str | None = None,
    campaign_id: str | None = None,
    niche: str | None = None,
    product_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[PinPerformance]:
    stmt = select(PinPerformance).order_by(PinPerformance.created_at.desc()).offset(offset).limit(limit)
    if account_id:
        stmt = stmt.where(PinPerformance.account_id == account_id)
    if campaign_id:
        stmt = stmt.where(PinPerformance.campaign_id == campaign_id)
    if niche:
        stmt = stmt.where(PinPerformance.niche == niche)
    if product_type:
        stmt = stmt.where(PinPerformance.product_type == product_type)
    return list(db.scalars(stmt).all())


@router.get("/pins/{pin_id}", response_model=PinPerformanceRead)
def get_pin_performance(pin_id: int, db: Session = Depends(get_db)) -> PinPerformance:
    record = db.get(PinPerformance, pin_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pin performance not found")
    return record


@router.post("/pins/{pin_id}/metrics", response_model=PinPerformanceRead)
def update_metrics(pin_id: int, payload: PinMetricsUpdate, db: Session = Depends(get_db)) -> PinPerformance:
    try:
        return update_pin_metrics(db, pin_id=pin_id, **payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary(
    account_id: str | None = None,
    campaign_id: str | None = None,
    niche: str | None = None,
    product_type: str | None = None,
    db: Session = Depends(get_db),
) -> AnalyticsSummary:
    stmt = select(PinPerformance)
    if account_id:
        stmt = stmt.where(PinPerformance.account_id == account_id)
    if campaign_id:
        stmt = stmt.where(PinPerformance.campaign_id == campaign_id)
    if niche:
        stmt = stmt.where(PinPerformance.niche == niche)
    if product_type:
        stmt = stmt.where(PinPerformance.product_type == product_type)

    rows = list(db.scalars(stmt.limit(2000)).all())
    keyword_counter: Counter[str] = Counter()
    for row in rows:
        keyword_counter.update(row.keywords or [])

    totals = {
        "pin_count": len(rows),
        "impressions": sum(row.impressions for row in rows),
        "clicks": sum(row.clicks for row in rows),
        "saves": sum(row.saves for row in rows),
        "outbound_clicks": sum(row.outbound_clicks for row in rows),
        "comments": sum(row.comments for row in rows),
        "reactions": sum(row.reactions for row in rows),
    }
    impressions = totals["impressions"]
    return AnalyticsSummary(
        **totals,
        avg_ctr=totals["clicks"] / impressions if impressions else 0.0,
        avg_save_rate=totals["saves"] / impressions if impressions else 0.0,
        avg_engagement_rate=(totals["saves"] + totals["comments"] + totals["reactions"]) / impressions
        if impressions
        else 0.0,
        top_keywords=[
            {"keyword": keyword, "count": count}
            for keyword, count in keyword_counter.most_common(20)
        ],
    )
