from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrendSignal:
    keyword: str
    source: str
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CurrentEventsTrendClient:
    """Placeholder for approved current-event trend providers."""

    async def fetch(self, *, query: str | None = None, limit: int = 20) -> list[TrendSignal]:
        logger.info("Current-events trend provider is not configured", extra={"query": query, "limit": limit})
        return []


class ProductTrendClient:
    """Placeholder for approved POD/product trend providers."""

    async def fetch(
        self,
        *,
        niche: str | None = None,
        product_type: str | None = None,
        limit: int = 20,
    ) -> list[TrendSignal]:
        logger.info(
            "Product trend provider is not configured",
            extra={"niche": niche, "product_type": product_type, "limit": limit},
        )
        return []
