from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrendSignal:
    keyword: str
    source: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrendFetchResult:
    provider: str
    status: str
    signals: list[TrendSignal]
    metadata: dict[str, Any] = field(default_factory=dict)


class PinterestTrendProvider:
    """Pinterest trend provider shell.

    The project does not assume a specific Pinterest trend endpoint yet. When
    API access is approved, inject a test client or implement the endpoint
    mapping inside ``fetch`` without changing the workflow contract.
    """

    provider_name = "pinterest"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        enabled: bool | None = None,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.pinterest_api_key
        self.enabled = enabled if enabled is not None else settings.pinterest_trends_enabled
        self.base_url = (base_url or settings.pinterest_trends_base_url).rstrip("/")
        self.http_client = http_client

    async def fetch(
        self,
        *,
        query: str | None = None,
        niche: str | None = None,
        product_type: str | None = None,
        limit: int = 20,
        trend_type: str = "product",
    ) -> TrendFetchResult:
        context = {
            "query": query,
            "niche": niche,
            "product_type": product_type,
            "limit": limit,
            "trend_type": trend_type,
        }
        if not self.enabled or not self.api_key:
            logger.info("Pinterest trend provider is not configured", extra=context)
            return TrendFetchResult(
                provider=self.provider_name,
                status="not_configured",
                signals=[],
                metadata=context,
            )

        # Placeholder endpoint shape for future Pinterest API access. Tests can
        # inject an http_client and assert normalization without real network.
        params = {
            "query": query or niche or product_type or "",
            "limit": limit,
            "trend_type": trend_type,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        owns_client = self.http_client is None
        client = self.http_client or httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.get(f"{self.base_url}/trends", params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Pinterest trend fetch failed: %s", exc)
            return TrendFetchResult(
                provider=self.provider_name,
                status="error",
                signals=[],
                metadata=context | {"error": str(exc)},
            )
        finally:
            if owns_client:
                await client.aclose()

        signals = _normalize_pinterest_payload(payload, trend_type=trend_type)
        return TrendFetchResult(
            provider=self.provider_name,
            status="ok",
            signals=signals[:limit],
            metadata=context | {"raw_count": len(signals)},
        )


def _normalize_pinterest_payload(payload: Any, *, trend_type: str) -> list[TrendSignal]:
    if isinstance(payload, dict):
        raw_items = payload.get("trends") or payload.get("items") or payload.get("data") or []
    elif isinstance(payload, list):
        raw_items = payload
    else:
        raw_items = []

    signals: list[TrendSignal] = []
    for item in raw_items:
        if isinstance(item, str):
            keyword = item
            weight = 1.0
            metadata: dict[str, Any] = {"trend_type": trend_type}
        elif isinstance(item, dict):
            keyword = str(
                item.get("keyword")
                or item.get("term")
                or item.get("query")
                or item.get("name")
                or ""
            )
            weight = _coerce_weight(item.get("weight") or item.get("score") or item.get("volume"))
            metadata = {"trend_type": trend_type, "raw": item}
        else:
            continue
        keyword = " ".join(keyword.split())
        if keyword:
            signals.append(
                TrendSignal(
                    keyword=keyword,
                    source="pinterest",
                    weight=weight,
                    metadata=metadata,
                )
            )
    return signals


def _coerce_weight(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 1.0
    return max(parsed, 0.0)


class CurrentEventsTrendClient:
    """Pinterest-backed current-event trend client."""

    async def fetch(self, *, query: str | None = None, limit: int = 20) -> list[TrendSignal]:
        return (await self.fetch_result(query=query, limit=limit)).signals

    async def fetch_result(self, *, query: str | None = None, limit: int = 20) -> TrendFetchResult:
        return await PinterestTrendProvider().fetch(
            query=query,
            limit=limit,
            trend_type="current_events",
        )


class ProductTrendClient:
    """Pinterest-backed POD/product trend client."""

    async def fetch(
        self,
        *,
        niche: str | None = None,
        product_type: str | None = None,
        limit: int = 20,
    ) -> list[TrendSignal]:
        return (
            await self.fetch_result(niche=niche, product_type=product_type, limit=limit)
        ).signals

    async def fetch_result(
        self,
        *,
        niche: str | None = None,
        product_type: str | None = None,
        limit: int = 20,
    ) -> TrendFetchResult:
        return await PinterestTrendProvider().fetch(
            niche=niche,
            product_type=product_type,
            limit=limit,
            trend_type="product",
        )
