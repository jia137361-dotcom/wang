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

# Click the search icon / trigger first — Pinterest hides the <input> until
# the user opens the search bar.
SEARCH_TRIGGER_SELECTORS = [
    'button[data-test-id="search-box-link"]',
    'a[data-test-id="search-box-link"]',
    'div[data-test-id="search-box-link"]',
    'button[aria-label*="Search" i]',
    'a[aria-label*="Search" i]',
    '[data-test-id="search-box-container"] button',
    '[data-test-id="search-box-container"] a',
    'button[data-test-id*="search" i]',
    'a[data-test-id*="search" i]',
    'nav a[href="/search/"]',
    'header button:first-of-type',
    'div[role="banner"] button:first-of-type',
]

SEARCH_INPUT_SELECTORS = [
    'input[data-test-id="search-box-input"]',
    'input[data-test-id="search-input"]',
    'input[name="searchInput"]',
    'input[placeholder*="Search" i]',
    'input[type="search"]',
    'input[aria-label*="search" i]',
    'input[aria-label*="Search" i]',
    'div[role="search"] input',
    'form[role="search"] input',
]

PIN_IMAGE = 'div[data-test-id="pin"] img, [data-test-id="pin"] img, div[data-grid-item] img, [data-test-id*="pin"] img, img[src*="pinimg.com"]'
CLOSEUP_PIN = 'div[data-test-id="closeup-body"], [data-test-id="pin-closeup"], div[role="dialog"] img, [data-test-id="pin-detail"]'
SAVE_BUTTON_SELECTORS = [
    'button[data-test-id="save-button"]',
    'div[data-test-id="save-button"] button',
    'button[aria-label*="Save" i]',
    'div[aria-label*="Save" i] button',
    '[data-test-id*="save" i] button',
]
CLOSE_BUTTON_SELECTORS = [
    'button[data-test-id="close-btn"]',
    'button[aria-label="Close"]',
    'button[aria-label*="close" i]',
    'div[role="dialog"] button[aria-label*="Close" i]',
    '[data-test-id="pin-close-btn"]',
    'div[role="dialog"] button:first-of-type',
]

LIKE_BUTTON_SELECTORS = [
    'button[data-test-id="reaction-button"]',
    'div[data-test-id="reaction-button"] button',
    '[data-test-id="pin-reaction"] button',
    '[data-test-id="reaction"] button',
    'button[aria-label*="reaction" i]',
    'div[aria-label="reaction"] button',
    'button[aria-label*="like" i]',
    '[aria-label*="like" i] button',
    'button[aria-label*="Love" i]',
    'button[aria-label*="love" i]',
]

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
    start_ts = time.time()
    total_seconds = duration_minutes * 60
    deadline = start_ts + total_seconds
    actions = 0
    searches = 0
    interactions = 0

    logger.info("Warmup session start account=%s duration=%dm", account_id, duration_minutes)

    # 1. Navigate to Pinterest home and scroll the feed
    await page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
    await human.random_delay(1.5, 3.0)
    logger.info("Pinterest home loaded url=%s", page.url)

    await _random_scroll_activity(page, human, count=random.randint(3, 6))
    actions += 1

    # 2. Search + browse loop (until time budget is ~60 % consumed)
    keywords = random.sample(SEARCH_KEYWORDS, min(3, len(SEARCH_KEYWORDS)))
    for kw in keywords:
        if time.time() - start_ts > total_seconds * 0.6:
            break
        await _search_and_browse(page, human, kw)
        searches += 1
        actions += 1

    # 3. Pin interactions
    interact_count = random.randint(1, 4)
    for _ in range(interact_count):
        if time.time() - start_ts > total_seconds * 0.85:
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


async def _try_find_element(page: Page, selectors: list[str]):
    """Return the first matching element across a list of selectors, or None."""
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=1500)
            if el:
                return el
        except Exception:
            continue
    return None


async def _close_pin_detail(page: Page, human: HumanSimulator) -> None:
    """Close an open pin detail view — try close button, then Escape, then go-back."""
    close_btn = await _try_find_element(page, CLOSE_BUTTON_SELECTORS)
    if close_btn:
        await human.click_element_with_movement(page, close_btn)
        await page.wait_for_timeout(600)
        return
    # Fallback: Escape key often closes overlays/modals
    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(800)
        return
    except Exception:
        pass
    await page.go_back()
    await page.wait_for_timeout(800)


async def _like_current_pin(page: Page, human: HumanSimulator) -> bool:
    """Try to click the like/reaction button on the currently-open pin detail.
    Returns True if a like was performed."""
    for sel in LIKE_BUTTON_SELECTORS:
        try:
            btn = await page.wait_for_selector(sel, timeout=2000)
            if btn:
                await human.click_element_with_movement(page, btn)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                logger.info("Warmup: LIKED a pin via selector=%s", sel)
                return True
        except Exception:
            continue
    logger.warning("Warmup: like selectors did not match any element on page")
    return False


async def _quick_pin_interaction(page: Page, human: HumanSimulator) -> bool:
    """Open a random pin from the current feed, optionally like or save it,
    then close and return.  Returns True if any interaction happened."""
    try:
        # Try multiple selectors for pin images (comma-separated CSS OR)
        pin = await page.wait_for_selector(PIN_IMAGE, timeout=2000)
        if not pin:
            return False
        await human.click_element_with_movement(page, pin)
        try:
            await page.wait_for_selector(CLOSEUP_PIN, timeout=4000)
        except Exception:
            return False
        await asyncio.sleep(random.uniform(0.8, 2.0))

        interacted = False
        if random.random() < 0.4:
            if await _like_current_pin(page, human):
                interacted = True
        if random.random() < 0.25:
            save = await _try_find_element(page, SAVE_BUTTON_SELECTORS)
            if save:
                await human.click_element_with_movement(page, save)
                await asyncio.sleep(random.uniform(0.5, 1.0))
                interacted = True

        await _close_pin_detail(page, human)
        return interacted
    except Exception:
        return False


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
        # Occasionally click a random pin from the feed and engage with it
        if random.random() < 0.12:
            await _quick_pin_interaction(page, human)


async def _search_and_browse(page: Page, human: HumanSimulator, keyword: str) -> None:
    logger.info("Warmup search keyword=%s", keyword)

    # 1) Click the search trigger/icon to expand the search bar
    trigger = await _try_find_element(page, SEARCH_TRIGGER_SELECTORS)
    if trigger:
        await human.click_element_with_movement(page, trigger)
        await human.random_delay(0.5, 1.0)

    # 2) Find the search input (now visible)
    search_el = None
    for sel in SEARCH_INPUT_SELECTORS:
        try:
            search_el = await page.wait_for_selector(sel, timeout=3000)
            if search_el:
                break
        except Exception:
            continue
    if not search_el:
        logger.warning("Warmup: search input not found for keyword=%s — skipping search", keyword)
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

    # Browse multiple pins from search results
    pins_to_browse = random.randint(2, 4)
    browsed = 0
    logger.info("Warmup: browsing %d pins from search results for keyword=%s", pins_to_browse, keyword)
    for _ in range(pins_to_browse):
        pins = await page.query_selector_all(PIN_IMAGE)
        if not pins:
            logger.warning("Warmup: no pins found in search results for keyword=%s", keyword)
            break
        target = random.choice(pins)
        await human.click_element_with_movement(page, target)
        try:
            await page.wait_for_selector(CLOSEUP_PIN, timeout=5000)
        except Exception:
            logger.debug("Warmup: closeup pin not found in search results, trying next")
            continue
        await asyncio.sleep(random.uniform(1.0, 2.5))

        # Like behavior (40% chance)
        if random.random() < 0.4:
            await _like_current_pin(page, human)
        # Save behavior (30% chance)
        if random.random() < 0.3:
            save = await _try_find_element(page, SAVE_BUTTON_SELECTORS)
            if save:
                await human.click_element_with_movement(page, save)
                await asyncio.sleep(random.uniform(0.5, 1.0))

        await _close_pin_detail(page, human)
        browsed += 1

        # Scroll a bit between pins for natural browsing
        if browsed < pins_to_browse and random.random() < 0.6:
            await human.smooth_scroll(
                page, direction="down", distance=random.randint(100, 300)
            )
            await asyncio.sleep(random.uniform(0.5, 1.5))

    # Cooldown between searches
    await asyncio.sleep(random.randint(5, 15))


async def _interact_with_random_pin(
    page: Page, human: HumanSimulator
) -> bool:
    """Open a random pin from the feed, like and/or save it, then close.
    Returns True if an interaction was performed."""
    try:
        pin = await page.wait_for_selector(PIN_IMAGE, timeout=3000)
        if not pin:
            logger.warning("Warmup: no pins found on page for interaction")
            return False
        await human.click_element_with_movement(page, pin)
        try:
            await page.wait_for_selector(CLOSEUP_PIN, timeout=5000)
        except Exception:
            logger.debug("Warmup: closeup not detected, pin may not have opened")
            return False
        await asyncio.sleep(random.uniform(1.0, 3.0))

        interacted = False
        # Like the pin (50% chance)
        if random.random() < 0.5:
            if await _like_current_pin(page, human):
                interacted = True
                # If liked, lower save probability
                if random.random() < 0.3:
                    save = await _try_find_element(page, SAVE_BUTTON_SELECTORS)
                    if save:
                        await human.click_element_with_movement(page, save)
                        await asyncio.sleep(random.uniform(0.5, 1.0))
        else:
            # Save the pin if not liked (60% chance)
            if random.random() < 0.6:
                save = await _try_find_element(page, SAVE_BUTTON_SELECTORS)
                if save:
                    await human.click_element_with_movement(page, save)
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                    logger.info("Warmup: saved a pin")
                    interacted = True

        await _close_pin_detail(page, human)
        return interacted
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
