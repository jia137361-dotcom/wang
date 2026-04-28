from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.evomap.strategy_matrix import get_strategy, upsert_strategy
from app.tools.trend_sources import CurrentEventsTrendClient, ProductTrendClient, TrendSignal


async def refresh_current_event_trends(
    db: Session,
    *,
    scope: str,
    query: str | None = None,
    limit: int = 20,
) -> dict:
    """刷新时事趋势；外部数据源未配置时会写入空结果快照。"""
    signals = await CurrentEventsTrendClient().fetch(query=query, limit=limit)
    return _store_trend_signals(
        db,
        scope=scope,
        bucket="current_event_trends",
        source_type="current_events",
        signals=signals,
    )


async def refresh_product_trends(
    db: Session,
    *,
    scope: str,
    niche: str | None = None,
    product_type: str | None = None,
    limit: int = 20,
) -> dict:
    """刷新爆品趋势；外部数据源未配置时会写入空结果快照。"""
    signals = await ProductTrendClient().fetch(niche=niche, product_type=product_type, limit=limit)
    return _store_trend_signals(
        db,
        scope=scope,
        bucket="product_trends",
        source_type="product_trends",
        signals=signals,
    )


def _store_trend_signals(
    db: Session,
    *,
    scope: str,
    bucket: str,
    source_type: str,
    signals: list[TrendSignal],
) -> dict:
    strategy = get_strategy(db, scope)
    normalized = [
        {
            "keyword": " ".join(signal.keyword.lower().split()),
            "source": signal.source,
            "weight": signal.weight,
            "metadata": signal.metadata,
        }
        for signal in signals
        if signal.keyword.strip()
    ]
    strategy[bucket] = normalized
    strategy["trend_keywords"] = sorted({item["keyword"] for item in normalized})

    history = strategy.get("trend_history", [])
    history.append(
        {
            "source": source_type,
            "count": len(normalized),
            "recorded_at": datetime.now(UTC).isoformat(),
        }
    )
    strategy["trend_history"] = history[-50:]
    upsert_strategy(db, scope, strategy, version=strategy.get("version", source_type))
    return strategy
