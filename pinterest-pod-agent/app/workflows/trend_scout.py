from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.evomap.strategy_matrix import get_strategy, upsert_strategy


def record_manual_trends(
    db: Session,
    *,
    scope: str,
    keywords: list[str],
    source: str = "manual",
) -> dict:
    """Store manually approved trend keywords.

    This workflow intentionally avoids scraping or bypassing site limits. Trend
    data should come from approved internal research or manual entry.
    """

    cleaned = sorted({" ".join(keyword.lower().split()) for keyword in keywords if keyword.strip()})
    strategy = get_strategy(db, scope)
    trend_history = strategy.get("trend_history", [])
    trend_history.append(
        {
            "source": source,
            "keywords": cleaned,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
    )
    existing_keywords = set(strategy.get("trend_keywords", []))
    existing_keywords.update(cleaned)
    strategy["trend_keywords"] = sorted(existing_keywords)
    strategy["trend_history"] = trend_history[-20:]
    upsert_strategy(db, scope, strategy, version=strategy.get("version", "manual-trends"))
    return strategy


def get_recorded_trends(db: Session, *, scope: str) -> list[str]:
    strategy = get_strategy(db, scope)
    keywords = strategy.get("trend_keywords", [])
    return [keyword for keyword in keywords if isinstance(keyword, str)]
