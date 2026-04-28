from __future__ import annotations

from dataclasses import dataclass


class ReplyProviderNotConfigured(RuntimeError):
    """Raised when no approved comment/reply provider has been configured."""


@dataclass(frozen=True)
class SocialComment:
    comment_id: str
    account_id: str
    author_name: str | None
    text: str
    post_url: str | None = None


@dataclass(frozen=True)
class ReplyPostResult:
    comment_id: str
    reply_text: str
    posted: bool
    raw: dict


class PinterestReplyClient:
    """Placeholder for first-party or approved Pinterest reply integration."""

    async def fetch_unreplied_comments(self, *, account_id: str, limit: int = 20) -> list[SocialComment]:
        return []

    async def publish_reply(self, *, comment_id: str, reply_text: str) -> ReplyPostResult:
        raise ReplyProviderNotConfigured(
            "Pinterest reply provider is not configured. Fill PinterestReplyClient.publish_reply later."
        )
