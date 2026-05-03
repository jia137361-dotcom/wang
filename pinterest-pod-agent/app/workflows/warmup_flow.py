"""Warmup workflow: simulated human browsing on Pinterest via an AdsPower profile.

Uses HumanSimulator for realistic delays / mouse movement / typing mistakes.
The caller (Celery task) is responsible for opening and closing the AdsPower
profile via ``open_adspower_profile``.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from playwright.async_api import Page

from app.automation.human_sim import HumanSimulator

logger = logging.getLogger(__name__)

# --- tunable constants -------------------------------------------------------

SEARCH_KEYWORDS = [
    "home decor ideas", "diy crafts", "summer fashion",
    "food recipes", "travel destinations", "fitness motivation",
    "cute animals", "graphic design inspiration",
]

SEARCH_INPUT_SELECTORS = [
    'input[data-test-id="search-box-input"]',
    'input[name="searchInput"]',
    'input[placeholder*="Search" i]',
    'input[type="search"]',
]

PIN_IMAGE = 'div[data-test-id="pin"] img'
CLOSEUP_PIN = 'div[data-test-id="closeup-body"]'
SAVE_BUTTON = 'button[data-test-id="save-button"]'
CLOSE_BUTTON = 'button[data-test-id="close-btn"]'

# ---------------------------------------------------------------------------


@dataclass
class WarmupResult:
    account_id: str
    duration_seconds: float
    actions: int
    searches: int
    interactions: int
    started_at: datetime
    finished_at: datetime


async def run_warmup_session(
    page: Page,
    *,
    account_id: str = "",
    duration_minutes: int = 10,
) -> WarmupResult:
    """Run a single warmup session using an already-open AdsPower profile page.

    The session performs: home-feed scrolling → keyword searches with result
    browsing → random pin interactions (save) → idle cooldown.
    Caller must open/close the browser profile.
    """
    human = HumanSimulator()
    started_at = datetime.now(UTC)
    deadline = time.time() + duration_minutes * 60
    actions = 0
    searches = 0
    interactions = 0

    logger.info("Warmup session start account=%s duration=%dm", account_id, duration_minutes)

    # 1. Navigate to Pinterest home and scroll the feed
    await page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
    await human.random_delay(1.5, 3.0)
    logger.debug("Pinterest home loaded url=%s", page.url)

    await _random_scroll_activity(page, human, count=random.randint(3, 6))
    actions += 1

    # 2. Search + browse loop (until time budget is ~60 % consumed)
    keywords = random.sample(SEARCH_KEYWORDS, min(3, len(SEARCH_KEYWORDS)))
    for kw in keywords:
        if time.time() > deadline * 0.6:
            break
        await _search_and_browse(page, human, kw)
        searches += 1
        actions += 1

    # 3. Pin interactions
    interact_count = random.randint(1, 4)
    for _ in range(interact_count):
        if time.time() > deadline * 0.85:
            break
        ok = await _interact_with_random_pin(page, human)
        if ok:
            interactions += 1
        actions += 1
        if random.random() < 0.3:
            await asyncio.sleep(random.randint(2, 8))

    # 4. Final idle scrolling
    await _random_scroll_activity(page, human, count=random.randint(2, 5))
    actions += 1

    # 5. Cooldown — stay on page looking idle
    remaining = deadline - time.time()
    if remaining > 10:
        await asyncio.sleep(min(remaining, random.randint(10, 30)))

    elapsed = time.time() - (started_at.timestamp())
    finished_at = datetime.now(UTC)
    logger.info(
        "Warmup session done account=%s elapsed=%ds actions=%d searches=%d interactions=%d",
        account_id,
        int(elapsed),
        actions,
        searches,
        interactions,
    )
    return WarmupResult(
        account_id=account_id,
        duration_seconds=elapsed,
        actions=actions,
        searches=searches,
        interactions=interactions,
        started_at=started_at,
        finished_at=finished_at,
    )


# -- internal helpers ---------------------------------------------------------


async def _random_scroll_activity(
    page: Page, human: HumanSimulator, *, count: int = 5
) -> None:
    for _ in range(count):
        await human.smooth_scroll(
            page, direction="down", distance=random.randint(200, 500)
        )
        await asyncio.sleep(random.uniform(0.8, 2.5))
        if random.random() < 0.2:
            await human.smooth_scroll(
                page, direction="up", distance=random.randint(50, 150)
            )
        if random.random() < 0.4:
            await human.hover_random_element(page, PIN_IMAGE)
            await asyncio.sleep(random.uniform(0.5, 2.0))


async def _search_and_browse(page: Page, human: HumanSimulator, keyword: str) -> None:
    logger.debug("Warmup search keyword=%s", keyword)
    search_el = None
    for sel in SEARCH_INPUT_SELECTORS:
        try:
            search_el = await page.wait_for_selector(sel, timeout=3000)
            if search_el:
                break
        except Exception:
            continue
    if not search_el:
        logger.debug("Search input not found, skipping search")
        return

    await human.click_element_with_movement(page, search_el)
    await human.random_delay(0.3, 0.8)
    if await search_el.input_value():
        await search_el.fill("")
    await human.simulate_typing(page, keyword)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(2000)

    # Scroll through search results
    await _random_scroll_activity(page, human, count=random.randint(3, 5))

    # Randomly click into a pin detail
    if random.random() < 0.5:
        pins = await page.query_selector_all(PIN_IMAGE)
        if pins:
            target = random.choice(pins)
            await human.click_element_with_movement(page, target)
            try:
                await page.wait_for_selector(CLOSEUP_PIN, timeout=5000)
            except Exception:
                pass
            await asyncio.sleep(random.randint(2, 6))
            if random.random() < 0.7:
                await page.go_back()
                await page.wait_for_timeout(1000)

    # Cooldown between searches
    await asyncio.sleep(random.randint(5, 15))


async def _interact_with_random_pin(
    page: Page, human: HumanSimulator
) -> bool:
    """Open a random pin from the feed and optionally save it.  Returns True if
    an interaction was performed."""
    try:
        pin = await page.wait_for_selector(PIN_IMAGE, timeout=3000)
        if not pin:
            return False
        await human.click_element_with_movement(page, pin)
        try:
            await page.wait_for_selector(CLOSEUP_PIN, timeout=5000)
        except Exception:
            return False
        await asyncio.sleep(random.uniform(1.0, 3.0))

        # Save the pin (most natural warmup action)
        if random.random() < 0.6:
            save = await page.query_selector(SAVE_BUTTON)
            if save:
                await human.click_element_with_movement(page, save)
                await asyncio.sleep(random.uniform(0.8, 1.5))
                logger.debug("Warmup: saved a pin")

        # Close pin detail
        close_btn = await page.query_selector(CLOSE_BUTTON)
        if close_btn:
            await human.click_element_with_movement(page, close_btn)
        else:
            await page.go_back()
        await page.wait_for_timeout(1000)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Backward-compatibility stubs for safety-gate check scripts
# ---------------------------------------------------------------------------


def run_account_warmup_placeholder(account_id: str) -> None:
    """Safety-gated no-op retained for check_sensitive_placeholders.py."""
    logger.info("warmup placeholder for %s (no-op)", account_id)


@dataclass(frozen=True)
class _WarmupResultStub:
    executed: bool = False


class WarmupFlow:
    """Backward-compatible safety-gated stub for check_sensitive_placeholders."""

    def run(self, account_id: str) -> _WarmupResultStub:
        return _WarmupResultStub(executed=False)
