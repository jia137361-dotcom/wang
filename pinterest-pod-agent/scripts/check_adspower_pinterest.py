import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.automation.browser_factory import open_adspower_profile
from app.tools.adspower_api import AdsPowerClient


PROFILE_ID = "k1buvn6c"


async def main() -> None:
    client = AdsPowerClient()
    endpoint = client.get_playwright_endpoint(PROFILE_ID)
    print("has_ws", bool(endpoint))
    session = await open_adspower_profile(PROFILE_ID, adspower_client=client)
    try:
        await session.page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
        print("url", session.page.url)
        print("title", await session.page.title())
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
