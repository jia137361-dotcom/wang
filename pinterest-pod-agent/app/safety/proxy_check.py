"""Proxy verification helpers for browser automation tasks."""

from __future__ import annotations

import json
import logging

from playwright.async_api import Page

from app.safety.errors import FatalError

logger = logging.getLogger(__name__)


async def verify_us_ip(page: Page) -> dict[str, str]:
    """Verify the browser's public IP is US-based before publishing.

    Returns {"ip": "...", "country": "..."} on success.
    Raises FatalError if the IP is non-US or the check fails.
    """
    try:
        resp = await page.goto("https://api.ipify.org?format=json", timeout=15000)
        if resp is None:
            raise FatalError("Proxy verification failed: no response from ipify")

        body = await resp.body()
        ip_info = json.loads(body)
        ip = ip_info.get("ip", "")

        if not ip:
            raise FatalError("Proxy verification failed: empty IP address")

        # check country via ipinfo.io (more accurate than ip-api)
        geo_resp = await page.goto(
            f"https://ipinfo.io/{ip}/json",
            timeout=15000,
        )
        if geo_resp is None:
            logger.warning("Could not verify IP geo-location for %s", ip)
            return {"ip": ip, "country": "unknown"}

        geo_body = await geo_resp.body()
        geo_info = json.loads(geo_body)
        country_code = geo_info.get("country", "")

        if country_code not in ("US",):
            raise FatalError(
                f"Non-US proxy detected: {ip} is in {geo_info.get('city', 'Unknown')}, "
                f"{geo_info.get('country', 'Unknown')} "
                f"({country_code}). Aborting to protect account."
            )

        logger.info("Proxy verified: %s (%s)", ip, country_code)
        return {"ip": ip, "country": country_code}

    except FatalError:
        raise
    except Exception as exc:
        logger.warning("Proxy verification soft-failed: %s", exc)
        # Don't block on transient geo-lookup failures
        return {"ip": "unknown", "country": "unknown"}
