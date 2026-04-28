from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.pin_performance import PinPerformance


def update_pin_metrics(
    db: Session,
    *,
    pin_id: int,
    impressions: int,
    saves: int,
    clicks: int,
    outbound_clicks: int = 0,
    comments: int = 0,
    reactions: int = 0,
) -> PinPerformance:
    record = db.get(PinPerformance, pin_id)
    if record is None:
        raise ValueError(f"PinPerformance not found: {pin_id}")

    record.impressions = impressions
    record.saves = saves
    record.clicks = clicks
    record.outbound_clicks = outbound_clicks
    record.comments = comments
    record.reactions = reactions
    record.metrics_updated_at = datetime.now(UTC)
    record.refresh_rates()
    db.commit()
    db.refresh(record)
    return record
