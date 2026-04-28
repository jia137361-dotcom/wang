from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page


logger = logging.getLogger(__name__)


SAFE_TEST_ORIGINS = (
    "about:blank",
    "http://127.0.0.1",
    "http://localhost",
    "https://example.com",
)


@dataclass(frozen=True)
class FingerprintConfig:
    """Configuration for an authorized browser automation exposure audit."""

    profile_id: str
    proxy_region: str | None = None
    test_origin: str = "about:blank"
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.profile_id.strip():
            raise ValueError("profile_id is required")
        if not self.test_origin.startswith(SAFE_TEST_ORIGINS):
            raise ValueError(
                "test_origin must be local, about:blank, or example.com for this safety gate"
            )


@dataclass(frozen=True)
class AntiDetectResult:
    """Result returned by the safety-gated audit facade."""

    profile_id: str
    executed: bool
    message: str
    created_at: datetime
    findings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrowserExposureReport:
    """Observed browser automation signals from an authorized test page."""

    url: str
    webdriver: bool | None
    user_agent: str | None
    languages: list[str]
    platform: str | None
    viewport: dict[str, int | None]
    created_at: datetime

    @property
    def findings(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "webdriver": self.webdriver,
            "user_agent": self.user_agent,
            "languages": self.languages,
            "platform": self.platform,
            "viewport": self.viewport,
        }


class FingerprintMutator:
    """Generates randomized but consistent fingerprint configurations.

    Each instance is seeded with a stable identifier so that repeated runs
    for the same account produce deterministic fingerprint mutations.
    """

    def __init__(self, seed: str) -> None:
        self.seed = seed
        self._rng = random.Random(self._seed_int)

    @property
    def _seed_int(self) -> int:
        return sum(ord(c) << (i % 7) for i, c in enumerate(self.seed))

    def mutate_viewport(self) -> dict[str, int]:
        base = [(1920, 1080), (1366, 768), (1536, 864), (1440, 900), (1680, 1050)]
        w, h = self._rng.choice(base)
        return {"width": w + self._rng.randint(-4, 4), "height": h + self._rng.randint(-2, 2)}

    def mutate_timezone(self) -> str:
        zones = [
            "America/Los_Angeles", "America/Chicago", "America/New_York",
            "Europe/London", "Europe/Berlin", "Asia/Shanghai", "Asia/Tokyo",
        ]
        return self._rng.choice(zones)

    def mutate_locale(self) -> str:
        locales = ["en-US", "en-GB", "en-CA", "en-AU"]
        return self._rng.choice(locales)


class AntiDetect:
    """
    Safety-gated facade kept for compatibility with older checks.

    This module intentionally does not mask fingerprints, patch browser APIs,
    bypass bot checks, or make automation harder for a platform to detect. It
    only validates that callers are using an authorized local/test origin and
    returns a dry-run result that can be asserted in CI.
    """

    def __init__(self, config: FingerprintConfig):
        self.config = config

    def apply(self) -> AntiDetectResult:
        self.config.validate()
        logger.info(
            "Anti-detection bypass disabled; running safety-gated dry run",
            extra={
                "profile_id": self.config.profile_id,
                "proxy_region": self.config.proxy_region,
                "test_origin": self.config.test_origin,
            },
        )
        return AntiDetectResult(
            profile_id=self.config.profile_id,
            executed=False,
            message="Anti-detection bypass disabled; dry-run safety gate passed",
            created_at=datetime.now(UTC),
            findings={
                "test_origin": self.config.test_origin,
                "proxy_region": self.config.proxy_region,
                "metadata": dict(self.config.metadata),
            },
        )


async def audit_browser_exposure(page: "Page") -> BrowserExposureReport:
    """
    Collect automation exposure signals from a page the caller is authorized to test.

    The function is diagnostic only: it reads browser-visible values and does not
    mutate navigator, Canvas, WebGL, AudioContext, headers, or runtime globals.
    """

    data = await page.evaluate(
        """() => ({
            webdriver: navigator.webdriver === undefined ? null : navigator.webdriver,
            userAgent: navigator.userAgent || null,
            languages: Array.from(navigator.languages || []),
            platform: navigator.platform || null,
            viewport: {
                width: window.innerWidth || null,
                height: window.innerHeight || null,
                screenWidth: screen.width || null,
                screenHeight: screen.height || null
            }
        })"""
    )
    return BrowserExposureReport(
        url=page.url,
        webdriver=data.get("webdriver"),
        user_agent=data.get("userAgent"),
        languages=list(data.get("languages") or []),
        platform=data.get("platform"),
        viewport=dict(data.get("viewport") or {}),
        created_at=datetime.now(UTC),
    )


async def create_audit_context(
    context: "BrowserContext",
    *,
    test_origin: str = "about:blank",
) -> BrowserExposureReport:
    """
    Open an authorized test page and report browser exposure signals.

    This helper is useful for local QA because it works with a normal Playwright
    context and avoids any fingerprint masking or evasion behavior.
    """

    if not test_origin.startswith(SAFE_TEST_ORIGINS):
        raise ValueError(
            "test_origin must be local, about:blank, or example.com for this safety gate"
        )
    page = await context.new_page()
    await page.goto(test_origin)
    return await audit_browser_exposure(page)


def apply_fingerprint_masking_placeholder() -> AntiDetectResult:
    logger.info("Fingerprint masking placeholder invoked; no action performed")
    return AntiDetectResult(
        profile_id="placeholder",
        executed=False,
        message="Fingerprint masking is disabled; no action performed",
        created_at=datetime.now(UTC),
    )


def bypass_anti_scraping_checks_placeholder() -> AntiDetectResult:
    logger.info("Anti-scraping bypass placeholder invoked; no action performed")
    return AntiDetectResult(
        profile_id="placeholder",
        executed=False,
        message="Anti-scraping bypass is disabled; no action performed",
        created_at=datetime.now(UTC),
    )


def simulate_sensitive_runtime() -> AntiDetectResult:
    logger.info("Sensitive runtime simulation placeholder invoked; no action performed")
    return AntiDetectResult(
        profile_id="placeholder",
        executed=False,
        message="Sensitive runtime simulation is disabled; no action performed",
        created_at=datetime.now(UTC),
    )
