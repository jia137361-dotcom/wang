from __future__ import annotations

from dataclasses import dataclass

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.tools.adspower_api import AdsPowerClient


@dataclass
class BrowserSession:
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page
    adspower_profile_id: str | None = None

    async def close(self) -> None:
        await self.browser.close()
        await self.playwright.stop()


async def connect_adspower_browser(
    playwright_ws_url: str,
    *,
    adspower_profile_id: str | None = None,
) -> BrowserSession:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.connect_over_cdp(playwright_ws_url)
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = context.pages[0] if context.pages else await context.new_page()
    return BrowserSession(
        playwright=playwright,
        browser=browser,
        context=context,
        page=page,
        adspower_profile_id=adspower_profile_id,
    )


async def open_adspower_profile(
    profile_id: str,
    *,
    adspower_client: AdsPowerClient | None = None,
) -> BrowserSession:
    client = adspower_client or AdsPowerClient()
    endpoint = client.get_playwright_endpoint(profile_id)
    return await connect_adspower_browser(endpoint, adspower_profile_id=profile_id)
