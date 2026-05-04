from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.evomap.strategy_matrix import get_strategy, upsert_strategy
from app.tools.trend_sources import CurrentEventsTrendClient, ProductTrendClient, TrendFetchResult, TrendSignal


async def refresh_current_event_trends(
    db: Session,
    *,
    scope: str,
    query: str | None = None,
    limit: int = 20,
) -> dict:
    """刷新时事趋势；外部数据源未配置时会写入空结果快照。"""
    fetch_result = await CurrentEventsTrendClient().fetch_result(query=query, limit=limit)
    return _store_trend_signals(
        db,
        scope=scope,
        bucket="current_event_trends",
        source_type="current_events",
        fetch_result=fetch_result,
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
    fetch_result = await ProductTrendClient().fetch_result(
        niche=niche, product_type=product_type, limit=limit
    )
    return _store_trend_signals(
        db,
        scope=scope,
        bucket="product_trends",
        source_type="product_trends",
        fetch_result=fetch_result,
    )


def _store_trend_signals(
    db: Session,
    *,
    scope: str,
    bucket: str,
    source_type: str,
    signals: list[TrendSignal] | None = None,
    fetch_result: TrendFetchResult | None = None,
) -> dict:
    strategy = get_strategy(db, scope)
    if fetch_result is not None:
        signals = fetch_result.signals
    signals = signals or []
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
            "provider": fetch_result.provider if fetch_result else "manual",
            "status": fetch_result.status if fetch_result else "ok",
            "recorded_at": datetime.now(UTC).isoformat(),
        }
    )
    strategy["trend_history"] = history[-50:]
    strategy["trend_source_status"] = {
        "bucket": bucket,
        "source": source_type,
        "provider": fetch_result.provider if fetch_result else "manual",
        "status": fetch_result.status if fetch_result else "ok",
        "metadata": fetch_result.metadata if fetch_result else {},
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    upsert_strategy(db, scope, strategy, version=strategy.get("version", source_type))
    return strategy
