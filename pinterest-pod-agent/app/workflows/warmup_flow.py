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
from urllib.parse import urlparse

from playwright.async_api import Page

from app.automation.human_sim import HumanSimulator
from app.config import get_settings

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
    enable_pin_engagement: bool | None = None,
    enable_save: bool | None = None,
) -> WarmupResult:
    """Run a single warmup session using an already-open AdsPower profile page.

    Loops until *deadline* (driven by *duration_minutes*), randomly picking
    one of three actions each round: home-feed scrolling, keyword search +
    result browsing, or pin interaction.  Caller must open/close the browser
    profile.
    """
    settings = get_settings()
    if enable_pin_engagement is None:
        enable_pin_engagement = settings.warmup_enable_pin_engagement
    if enable_save is None:
        enable_save = settings.warmup_enable_save

    human = HumanSimulator()
    started_at = datetime.now(UTC)
    start_ts = time.time()
    deadline = start_ts + duration_minutes * 60
    actions = 0
    searches = 0
    interactions = 0

    logger.info("Warmup session start account=%s duration=%dm", account_id, duration_minutes)

    # 1. Navigate to Pinterest home
    await page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
    await human.random_delay(1.5, 3.0)
    logger.info("Pinterest home loaded url=%s", page.url)

    # 2. Time-driven main loop — keep acting until deadline
    unused_keywords: list[str] = list(SEARCH_KEYWORDS)
    while time.time() < deadline - 3:  # leave room for final cooldown
        try:
            roll = random.random()
            if enable_pin_engagement and roll < 0.15:
                ok = await _interact_with_random_pin(page, human, enable_save=enable_save)
                actions += 1
                if ok:
                    interactions += 1
            elif roll < 0.65:
                scrolls = random.randint(2, 5)
                await _random_scroll_activity(
                    page, human, count=scrolls,
                    enable_pin_engagement=enable_pin_engagement, enable_save=enable_save,
                )
                actions += 1
            else:
                if not unused_keywords:
                    unused_keywords = list(SEARCH_KEYWORDS)
                kw = random.choice(unused_keywords)
                unused_keywords.remove(kw)
                await _search_and_browse(
                    page, human, kw,
                    enable_pin_engagement=enable_pin_engagement, enable_save=enable_save,
                )
                searches += 1
                actions += 1
        except Exception:
            logger.exception("Warmup action failed, continuing")
        await asyncio.sleep(random.uniform(1.0, 3.0))

    # 3. Cooldown — wait until the real deadline
    remaining = deadline - time.time()
    if remaining > 0:
        logger.info("Warmup cooldown %.1fs", remaining)
        await asyncio.sleep(remaining)
    await _return_to_pinterest_home(page)

    elapsed = time.time() - started_at.timestamp()
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


async def _quick_pin_interaction(
    page: Page,
    human: HumanSimulator,
    *,
    enable_save: bool,
) -> bool:
    """Open a random pin from the current feed, optionally like or save it,
    then close and return.  Returns True if any interaction happened."""
    try:
        pin = await _pick_safe_pin(page, timeout_ms=2000)
        if not pin:
            return False
        await human.click_element_with_movement(page, pin)
        if await _recover_if_external_navigation(page, context="quick_pin_interaction"):
            return False
        try:
            await page.wait_for_selector(CLOSEUP_PIN, timeout=4000)
        except Exception:
            return False
        await asyncio.sleep(random.uniform(0.8, 2.0))

        interacted = False
        if random.random() < 0.4:
            if await _like_current_pin(page, human):
                interacted = True
        if enable_save and random.random() < 0.25:
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
    page: Page,
    human: HumanSimulator,
    *,
    count: int = 5,
    enable_pin_engagement: bool,
    enable_save: bool,
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
        if enable_pin_engagement and random.random() < 0.12:
            await _quick_pin_interaction(page, human, enable_save=enable_save)


async def _search_and_browse(
    page: Page,
    human: HumanSimulator,
    keyword: str,
    *,
    enable_pin_engagement: bool,
    enable_save: bool,
) -> None:
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
    await _random_scroll_activity(
        page,
        human,
        count=random.randint(3, 5),
        enable_pin_engagement=enable_pin_engagement,
        enable_save=enable_save,
    )

    # Browse multiple pins from search results
    pins_to_browse = random.randint(2, 4)
    browsed = 0
    logger.info("Warmup: browsing %d pins from search results for keyword=%s", pins_to_browse, keyword)
    for _ in range(pins_to_browse):
        pins = await _safe_pin_elements(page)
        if not pins:
            logger.warning("Warmup: no pins found in search results for keyword=%s", keyword)
            break
        target = random.choice(pins)
        await human.click_element_with_movement(page, target)
        if await _recover_if_external_navigation(page, context="search_result_pin"):
            continue
        try:
            await page.wait_for_selector(CLOSEUP_PIN, timeout=5000)
        except Exception:
            logger.debug("Warmup: closeup pin not found in search results, trying next")
            continue
        await asyncio.sleep(random.uniform(1.0, 2.5))

        if enable_pin_engagement and random.random() < 0.4:
            await _like_current_pin(page, human)
        if enable_save and random.random() < 0.3:
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
    page: Page,
    human: HumanSimulator,
    *,
    enable_save: bool,
) -> bool:
    """Open a random pin from the feed, like and/or save it, then close.
    Returns True if an interaction was performed."""
    try:
        pin = await _pick_safe_pin(page, timeout_ms=3000)
        if not pin:
            logger.warning("Warmup: no pins found on page for interaction")
            return False
        await human.click_element_with_movement(page, pin)
        if await _recover_if_external_navigation(page, context="random_pin_interaction"):
            return False
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
                if enable_save and random.random() < 0.3:
                    save = await _try_find_element(page, SAVE_BUTTON_SELECTORS)
                    if save:
                        await human.click_element_with_movement(page, save)
                        await asyncio.sleep(random.uniform(0.5, 1.0))
        else:
            # Save the pin if not liked (60% chance)
            if enable_save and random.random() < 0.6:
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


def _is_pinterest_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host == "pinterest.com" or host.endswith(".pinterest.com")


async def _recover_if_external_navigation(page: Page, *, context: str) -> bool:
    if _is_pinterest_url(page.url):
        return False
    logger.warning("Warmup blocked external navigation context=%s url=%s", context, page.url)
    try:
        await page.go_back(wait_until="domcontentloaded", timeout=8_000)
        await page.wait_for_timeout(800)
    except Exception:
        await _return_to_pinterest_home(page)
    if not _is_pinterest_url(page.url):
        await _return_to_pinterest_home(page)
    return True


async def _return_to_pinterest_home(page: Page) -> None:
    if _is_pinterest_url(page.url) and urlparse(page.url).path in {"", "/"}:
        return
    await page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
    await page.wait_for_timeout(800)


async def _pick_safe_pin(page: Page, *, timeout_ms: int):
    try:
        await page.wait_for_selector(PIN_IMAGE, timeout=timeout_ms)
    except Exception:
        return None
    pins = await _safe_pin_elements(page)
    if not pins:
        return None
    return random.choice(pins)


async def _safe_pin_elements(page: Page) -> list:
    pins = await page.query_selector_all(PIN_IMAGE)
    safe = []
    for pin in pins[:60]:
        try:
            is_safe = await pin.evaluate(
                """el => {
                    const blockedText = ['sponsored', 'shop now', 'shopping', 'amazon', 'etsy'];
                    const container = el.closest('a, [role="link"], [data-test-id="pin"], div[data-grid-item], [data-test-id*="pin" i]');
                    const hrefNode = el.closest('a[href]');
                    const href = (hrefNode && hrefNode.href || '').toLowerCase();
                    const text = (container && container.innerText || '').toLowerCase();
                    if (blockedText.some((item) => text.includes(item) || href.includes(item))) {
                        return false;
                    }
                    if (href && !href.includes('pinterest.com') && !href.startsWith('/')) {
                        return false;
                    }
                    if (href.includes('/offsite/') || href.includes('/shopping/') || href.includes('/dp/')) {
                        return false;
                    }
                    return true;
                }"""
            )
            if is_safe:
                safe.append(pin)
        except Exception:
            continue
    return safe
