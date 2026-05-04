from __future__ import annotations

import asyncio

from app.tools.trend_sources import PinterestTrendProvider


def test_pinterest_provider_not_configured_returns_status() -> None:
    provider = PinterestTrendProvider(api_key=None, enabled=False)

    result = asyncio.run(provider.fetch(query="dog mom shirt", limit=10))

    assert result.provider == "pinterest"
    assert result.status == "not_configured"
    assert result.signals == []
    assert result.metadata["query"] == "dog mom shirt"


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "trends": [
                {"keyword": "Dog Mom Shirt", "score": 3.5},
                {"term": "Custom Pet Gift", "weight": 2},
            ]
        }


class FakeAsyncClient:
    async def get(self, *args, **kwargs) -> FakeResponse:
        return FakeResponse()


def test_pinterest_provider_normalizes_mock_response() -> None:
    provider = PinterestTrendProvider(
        api_key="test-key",
        enabled=True,
        base_url="https://example.test",
        http_client=FakeAsyncClient(),
    )

    result = asyncio.run(
        provider.fetch(niche="pet lovers", product_type="t-shirt", limit=10)
    )

    assert result.status == "ok"
    assert [signal.keyword for signal in result.signals] == [
        "Dog Mom Shirt",
        "Custom Pet Gift",
    ]
    assert result.signals[0].source == "pinterest"
    assert result.signals[0].weight == 3.5
