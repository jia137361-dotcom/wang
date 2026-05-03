"""Auto-reply flow: fetch comments, generate LLM replies, post via browser."""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict

from playwright.async_api import Page

from app.tools.reply_client import PinterestReplyClient, ReplyPostResult, SocialComment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplySuggestion:
    comment_id: str
    comment_text: str
    reply_text: str
    posted: bool = False


@dataclass(frozen=True)
class AutoReplyResult:
    account_id: str
    dry_run: bool
    suggestions: list[ReplySuggestion]
    posted: list[ReplyPostResult]


async def run_auto_reply_flow(
    *,
    account_id: str,
    page: Page | None = None,
    dry_run: bool = True,
    limit: int = 20,
    brand_voice: str | None = None,
    niche: str | None = None,
) -> AutoReplyResult:
    """Fetch unreplied comments, generate LLM replies, optionally post."""
    client = PinterestReplyClient(page=page)
    comments = await client.fetch_unreplied_comments(
        account_id=account_id, limit=limit
    )

    suggestions: list[ReplySuggestion] = []
    for comment in comments:
        reply_text = await _generate_reply(comment, brand_voice=brand_voice, niche=niche)
        suggestions.append(
            ReplySuggestion(
                comment_id=comment.comment_id,
                comment_text=comment.text,
                reply_text=reply_text,
                posted=False,
            )
        )

    if dry_run:
        return AutoReplyResult(
            account_id=account_id,
            dry_run=True,
            suggestions=suggestions,
            posted=[],
        )

    posted: list[ReplyPostResult] = []
    for suggestion in suggestions:
        # find the original comment to get its pin_url
        pin_url = next(
            (c.pin_url for c in comments if c.comment_id == suggestion.comment_id),
            None,
        )
        result = await client.publish_reply(
            comment_id=suggestion.comment_id,
            reply_text=suggestion.reply_text,
            pin_url=pin_url,
        )
        posted.append(result)

    return AutoReplyResult(
        account_id=account_id,
        dry_run=False,
        suggestions=suggestions,
        posted=posted,
    )


async def _generate_reply(
    comment: SocialComment,
    *,
    brand_voice: str | None = None,
    niche: str | None = None,
) -> str:
    """Generate a reply using LLM, falling back to a keyword-aware template."""
    llm_text = await _try_llm_reply(comment, brand_voice=brand_voice, niche=niche)
    if llm_text:
        return llm_text
    return _template_reply(comment, brand_voice=brand_voice, niche=niche)


async def _try_llm_reply(
    comment: SocialComment,
    *,
    brand_voice: str | None = None,
    niche: str | None = None,
) -> str | None:
    """Try generating a reply via Volcengine LLM. Returns None if unavailable."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.volc_api_key:
        logger.debug("No VOLC_API_KEY configured, skipping LLM reply generation")
        return None

    try:
        from app.tools.volc_client import ChatMessage, VolcClient

        client = VolcClient()
        voice_hint = f" You represent a {brand_voice} brand." if brand_voice else ""
        niche_hint = f" The brand specializes in {niche}." if niche else ""
        system_prompt = (
            f"You are a friendly social media manager for a Pinterest shop.{voice_hint}{niche_hint}"
            " Write short, warm, natural replies under 25 words. Never sound like a bot."
        )
        user_prompt = (
            f"A customer commented on our Pin: \"{comment.text}\"\n"
            f"Write a brief, friendly reply in English."
        )
        text = await client.agenerate_text(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.8,
            max_tokens=80,
        )
        return text.strip()
    except Exception as exc:
        logger.warning("LLM reply generation failed, using template: %s", exc)
        return None


def _template_reply(
    comment: SocialComment,
    *,
    brand_voice: str | None = None,
    niche: str | None = None,
) -> str:
    """Template fallback when LLM is not available."""
    voice = f" {brand_voice.strip()}" if brand_voice and brand_voice.strip() else ""
    niche_ref = f"fellow {niche} enthusiasts" if niche else "you"

    has_question = "?" in comment.text
    if has_question:
        return (
            f"Great question!{voice} We'll check on this and get back to {niche_ref}. "
            "Thanks for reaching out!"
        )
    return f"Thanks so much!{voice} We appreciate the love from {niche_ref}."
