"""Run a simulated human browsing + search session on Pinterest via AdsPower."""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.automation.browser_factory import open_adspower_profile
from app.automation.human_sim import HumanSimulator
from app.tools.adspower_api import AdsPowerClient

PROFILE_ID = "k1buvn6c"

SEARCH_KEYWORDS = [
    "home decor ideas", "diy crafts", "summer fashion",
    "food recipes", "travel destinations", "fitness motivation",
    "cute animals", "graphic design inspiration",
]

PIN_IMAGE = 'div[data-test-id="pin"] img'
# Pinterest search selectors — try multiple since the DOM varies
SEARCH_SELECTORS = [
    'input[name="searchInput"]',
    'input[data-test-id="search-box-input"]',
    'input[placeholder*="Search" i]',
    'input[aria-label*="Search" i]',
    'input[type="search"]',
    '[data-test-id="search-input"]',
]
CLOSEUP_PIN = 'div[data-test-id="closeup-body"]'


async def main() -> None:
    human = HumanSimulator()
    client = AdsPowerClient()

    print("Connecting to AdsPower profile...")
    session = await open_adspower_profile(PROFILE_ID, adspower_client=client)
    page = session.page

    try:
        # 1. Go to Pinterest home
        print("Navigating to Pinterest...")
        await page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
        await human.random_delay(1.5, 3.0)
        print(f"  -> {page.url}  |  title: {await page.title()}")

        # 2. Idle scrolling like a real person
        print("Random scrolling on home feed...")
        for i in range(random.randint(4, 7)):
            await human.smooth_scroll(page, direction="down", distance=random.randint(200, 500))
            await asyncio.sleep(random.uniform(0.8, 2.5))
            if random.random() < 0.2:
                await human.smooth_scroll(page, direction="up", distance=random.randint(50, 150))
            if random.random() < 0.5:
                await human.hover_random_element(page, PIN_IMAGE)
                await asyncio.sleep(random.uniform(0.5, 2.0))
            print(f"  scroll {i+1} done")

        # 3. Search and browse for 2-3 keywords
        keywords = random.sample(SEARCH_KEYWORDS, random.randint(2, 3))
        for kw in keywords:
            print(f"\nSearching: '{kw}' ...")
            search_el = None
            for sel in SEARCH_SELECTORS:
                try:
                    search_el = await page.wait_for_selector(sel, timeout=3000)
                    if search_el:
                        print(f"  found search via: {sel}")
                        break
                except Exception:
                    continue
            if not search_el:
                print("  search input not found with any selector, skip")
                continue
            await human.click_element_with_movement(page, search_el)
            await human.random_delay(0.3, 0.8)
            if await search_el.input_value():
                await search_el.fill("")
            await human.simulate_typing(page, kw)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(2000)

            # Scroll through results
            for j in range(random.randint(3, 5)):
                await human.smooth_scroll(page, direction="down", distance=random.randint(200, 400))
                await asyncio.sleep(random.uniform(0.8, 2.0))
                if random.random() < 0.4:
                    await human.hover_random_element(page, PIN_IMAGE)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
            print(f"  browsed results for '{kw}'")

            # Maybe click into a pin detail
            if random.random() < 0.6:
                pins = await page.query_selector_all(PIN_IMAGE)
                if pins:
                    target = random.choice(pins)
                    print(f"  opening a pin detail...")
                    await human.click_element_with_movement(page, target)
                    await page.wait_for_selector(CLOSEUP_PIN, timeout=5000)
                    await asyncio.sleep(random.randint(2, 6))
                    # Go back
                    await page.go_back()
                    await page.wait_for_timeout(1000)
                    print(f"  back to results")

            # Cooldown between searches
            cooldown = random.randint(5, 15)
            print(f"  cooling down {cooldown}s...")
            await asyncio.sleep(cooldown)

        # 4. Final idle scroll on home feed
        print("\nFinal idle browsing...")
        for i in range(random.randint(3, 6)):
            await human.smooth_scroll(page, direction="down", distance=random.randint(200, 500))
            await asyncio.sleep(random.uniform(1.0, 2.5))
        print("  done")

        print("\n=== Browsing session complete ===")

    finally:
        print("Closing browser connection...")
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
