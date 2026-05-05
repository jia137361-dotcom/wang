"""human_sim.py --- realistic human behavior simulation for browser automation.

Provides HumanSimulator: a facade that wraps Playwright interactions with
randomised delays, mouse movement, and typing with realistic mistake rates.
"""

from __future__ import annotations

import asyncio
import random

from playwright.async_api import Page


class HumanSimulator:
    """Realistic human behaviour simulator for Playwright browser automation.

    Injects random delays, mouse wandering, smooth scrolling, and typing
    with configurable mistake rates so that automated sessions appear more
    human-like during warmup or browsing flows.
    """

    def __init__(
        self,
        *,
        min_delay: float = 0.3,
        max_delay: float = 2.0,
        mistake_rate: float = 0.03,
    ) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.mistake_rate = mistake_rate

    # ------------------------------------------------------------------
    # public API (called by warmup_flow and other automation modules)
    # ------------------------------------------------------------------

    async def random_delay(self, low: float = 0.5, high: float = 3.0) -> None:
        """Sleep for a random duration between *low* and *high* seconds."""
        await asyncio.sleep(random.uniform(low, high))

    async def mouse_wander(self, page: Page, *, steps: int = 3) -> None:
        """Move the mouse to a few random positions on the page to simulate
        idle cursor movement."""
        try:
            vp = page.viewport_size
            w = (vp or {}).get("width", 1200) or 1200
            h = (vp or {}).get("height", 800) or 800
        except Exception:
            w, h = 1200, 800

        for _ in range(steps):
            x = random.randint(100, max(100, w - 100))
            y = random.randint(100, max(100, h - 100))
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.4))

    async def smooth_scroll(
        self, page: Page, *, direction: str = "down", distance: int = 400
    ) -> None:
        """Scroll in small increments to mimic a human using a trackpad or
        mouse wheel."""
        sign = 1 if direction == "down" else -1
        remaining = distance
        while remaining > 0:
            step = min(random.randint(40, 120), remaining)
            await page.mouse.wheel(0, sign * step)
            remaining -= step
            await asyncio.sleep(random.uniform(0.05, 0.2))

    async def hover_random_element(self, page: Page, selector: str) -> None:
        """Hover over a randomly chosen visible element matching *selector*."""
        try:
            elements = page.locator(selector)
            count = await elements.count()
            if count:
                idx = random.randint(0, count - 1)
                await elements.nth(idx).hover(timeout=2000)
        except Exception:
            pass

    async def click_element_with_movement(
        self, page: Page, element: object, *, offset: tuple[int, int] | None = None
    ) -> None:
        """Move the mouse toward the element centre (with optional jitter),
        then click."""
        try:
            box = await element.bounding_box()  # type: ignore[union-attr]
            if box is None:
                await element.click()  # type: ignore[union-attr]
                return

            target_x = box["x"] + box["width"] / 2 + random.randint(-3, 3)
            target_y = box["y"] + box["height"] / 2 + random.randint(-3, 3)
            if offset:
                target_x += offset[0]
                target_y += offset[1]

            # intermediate way-point for more natural movement
            mid_x = target_x + random.randint(-20, 20)
            mid_y = target_y + random.randint(-20, 20)
            await page.mouse.move(mid_x, mid_y)
            await asyncio.sleep(random.uniform(0.05, 0.2))
            await page.mouse.move(target_x, target_y)
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await page.mouse.click(target_x, target_y)
        except Exception:
            try:
                await element.click()  # type: ignore[union-attr]
            except Exception:
                pass

    async def click_random_element(self, page: Page, selector: str) -> bool:
        """Click a randomly chosen visible element matching *selector*.
        Returns True if a click was performed."""
        try:
            elements = page.locator(selector)
            count = await elements.count()
            if count:
                idx = random.randint(0, count - 1)
                element = elements.nth(idx)
                await self.click_element_with_movement(page, element)
                return True
        except Exception:
            pass
        return False

    async def simulate_typing(
        self,
        page: Page,
        text: str,
        *,
        mistake_rate: float | None = None,
    ) -> None:
        """Type *text* character by character with variable inter-key delays
        and occasional typos that are immediately backspaced and corrected."""
        rate = mistake_rate if mistake_rate is not None else self.mistake_rate
        for char in text:
            if random.random() < rate:
                # type a wrong character then delete it
                wrong = random.choice("abcdefghijklmnopqrstuvwxyz")
                await page.keyboard.type(wrong)
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.03, 0.1))
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.03, 0.15))
