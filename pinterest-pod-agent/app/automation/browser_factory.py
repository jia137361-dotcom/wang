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


async def launch_browser(headless: bool = True) -> Browser:
    playwright = await async_playwright().start()
    return await playwright.chromium.launch(headless=headless)


async def launch_browser_session(headless: bool = True) -> BrowserSession:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=headless)
    context = await browser.new_context()
    page = await context.new_page()
    return BrowserSession(playwright=playwright, browser=browser, context=context, page=page)


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


class BrowserPool:
    """Pool of browser sessions keyed by account id.

    Used by warmup orchestrators to acquire and release browser sessions
    without launching a fresh browser for every session.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}

    async def acquire(self, account_id: str) -> BrowserSession:
        if account_id in self._sessions:
            return self._sessions[account_id]
        session = await launch_browser_session(headless=False)
        self._sessions[account_id] = session
        return session

    async def release(self, account_id: str, session: BrowserSession) -> None:
        # keep session cached; caller decides when to close
        pass

    async def close_all(self) -> None:
        for session in self._sessions.values():
            await session.close()
        self._sessions.clear()


async def open_adspower_profile(
    profile_id: str,
    *,
    adspower_client: AdsPowerClient | None = None,
) -> BrowserSession:
    client = adspower_client or AdsPowerClient()
    endpoint = client.get_playwright_endpoint(profile_id)
    return await connect_adspower_browser(endpoint, adspower_profile_id=profile_id)
