"""Pinterest comment reply client using browser automation."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SocialComment:
    comment_id: str
    account_id: str
    author_name: str | None
    text: str
    pin_url: str | None = None


@dataclass(frozen=True)
class ReplyPostResult:
    comment_id: str
    reply_text: str
    posted: bool
    raw: dict


# -- selectors for extracting comments from Pinterest notifications page --
_NOTIF_URL = "https://www.pinterest.com/notifications/"
_COMMENT_ITEM = '[data-test-id="notification-comment"]'
_COMMENT_TEXT = '[data-test-id="comment-text"]'
_COMMENT_AUTHOR = '[data-test-id="comment-author-name"]'
_COMMENT_LINK = 'a[href*="/pin/"]'

# -- selectors for posting a reply on a pin page --
_REPLY_INPUT = 'textarea[placeholder*="comment" i], div[contenteditable="true"][role="textbox"]'
_REPLY_SUBMIT = 'button[type="submit"], button:has-text("Send")'


class ReplyProviderNotConfigured(RuntimeError):
    """Raised when the reply workflow cannot proceed (e.g. not logged in)."""


class PinterestReplyClient:
    """Comment reply client driven by browser automation.

    Must be used inside an already-authenticated Pinterest session.
    """

    def __init__(self, page: Page | None = None) -> None:
        self.page = page

    async def fetch_unreplied_comments(
        self, *, account_id: str, limit: int = 20
    ) -> list[SocialComment]:
        """Navigate to Pinterest notifications and extract recent comments."""
        if self.page is None:
            logger.warning("No browser page available for comment fetch")
            return []

        page = self.page
        try:
            await page.goto(_NOTIF_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

            comments: list[SocialComment] = []
            # Try common comment selectors
            items = await page.query_selector_all(_COMMENT_ITEM)
            if not items:
                # fallback: look for any notification containing a pin link
                items = await page.query_selector_all(
                    f'div:has(a[href*="/pin/"])'
                )

            for item in items[:limit]:
                try:
                    author_el = await item.query_selector(_COMMENT_AUTHOR)
                    author = await author_el.inner_text() if author_el else None

                    text_el = await item.query_selector(_COMMENT_TEXT)
                    if not text_el:
                        text_el = await item.query_selector("span, p")
                    text = await text_el.inner_text() if text_el else ""
                    text = text.strip()

                    link_el = await item.query_selector(_COMMENT_LINK)
                    pin_url = None
                    if link_el:
                        pin_url = await link_el.get_attribute("href")

                    if text and pin_url:
                        comment_id = f"cmt_{hashlib.sha256((text + str(pin_url)).encode()).hexdigest()[:16]}_0"
                        comments.append(
                            SocialComment(
                                comment_id=comment_id,
                                account_id=account_id,
                                author_name=author,
                                text=text,
                                pin_url=pin_url,
                            )
                        )
                except Exception:
                    continue

            logger.info("Fetched %d unreplied comments for account=%s", len(comments), account_id)
            return comments
        except Exception as exc:
            logger.warning("Failed to fetch comments for account=%s: %s", account_id, exc)
            return []

    async def publish_reply(
        self, *, comment_id: str, reply_text: str, pin_url: str | None = None
    ) -> ReplyPostResult:
        """Navigate to a Pin page and post a reply comment."""
        if self.page is None:
            raise ReplyProviderNotConfigured("No browser page available for reply posting")

        page = self.page
        try:
            if pin_url:
                await page.goto(pin_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

            # Find comment/reply input
            reply_input = await page.query_selector(_REPLY_INPUT)
            if not reply_input:
                # Try clicking "Add a comment" button first
                add_btn = await page.query_selector(
                    'button:has-text("Add a comment"), span:has-text("Comment")'
                )
                if add_btn:
                    await add_btn.click()
                    await page.wait_for_timeout(1000)
                reply_input = await page.wait_for_selector(_REPLY_INPUT, timeout=5000)

            if not reply_input:
                return ReplyPostResult(
                    comment_id=comment_id,
                    reply_text=reply_text,
                    posted=False,
                    raw={"error": "Reply input not found"},
                )

            await reply_input.click()
            await reply_input.fill(reply_text)
            await page.wait_for_timeout(500)

            submit_btn = await page.query_selector(_REPLY_SUBMIT)
            if submit_btn:
                await submit_btn.click()
                await page.wait_for_timeout(2000)

            logger.info("Posted reply for comment=%s", comment_id)
            return ReplyPostResult(
                comment_id=comment_id,
                reply_text=reply_text,
                posted=True,
                raw={"pin_url": pin_url},
            )
        except Exception as exc:
            logger.warning("Failed to post reply: %s", exc)
            return ReplyPostResult(
                comment_id=comment_id,
                reply_text=reply_text,
                posted=False,
                raw={"error": str(exc)},
            )
