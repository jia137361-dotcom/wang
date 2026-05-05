"""Auto-reply flow: fetch comments, generate LLM replies, post via browser."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from playwright.async_api import Page
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_sessionmaker
from app.models.reply_record import ReplyRecord
from app.tools.reply_client import PinterestReplyClient, ReplyPostResult, SocialComment

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplySuggestion:
    comment_id: str
    comment_text: str
    reply_text: str
    safety_status: str = "safe"
    safety_reason: str | None = None
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
    db: Session | None = None,
) -> AutoReplyResult:
    """Fetch unreplied comments, generate LLM replies, optionally post."""
    client = PinterestReplyClient(page=page)
    comments = await client.fetch_unreplied_comments(
        account_id=account_id, limit=limit
    )

    owns_db = db is None
    db = db or get_sessionmaker()()
    try:
        suggestions: list[ReplySuggestion] = []
        for comment in comments:
            existing = _get_reply_record(db, account_id=account_id, comment_id=comment.comment_id)
            if existing and existing.status in {"posted", "suggested", "manual_review"}:
                logger.info(
                    "Skipping previously handled comment=%s account=%s status=%s",
                    comment.comment_id,
                    account_id,
                    existing.status,
                )
                continue

            safety_status, safety_reason = classify_comment_safety(comment.text)
            if safety_status != "safe":
                _upsert_reply_record(
                    db,
                    comment=comment,
                    reply_text=None,
                    status="manual_review",
                    safety_status=safety_status,
                    safety_reason=safety_reason,
                )
                suggestions.append(
                    ReplySuggestion(
                        comment_id=comment.comment_id,
                        comment_text=comment.text,
                        reply_text="",
                        safety_status=safety_status,
                        safety_reason=safety_reason,
                        posted=False,
                    )
                )
                continue

            reply_text = await _generate_reply(comment, brand_voice=brand_voice, niche=niche)
            _upsert_reply_record(
                db,
                comment=comment,
                reply_text=reply_text,
                status="suggested",
                safety_status="safe",
                safety_reason=None,
            )
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
            if suggestion.safety_status != "safe" or not suggestion.reply_text:
                continue
            pin_url = next(
                (c.pin_url for c in comments if c.comment_id == suggestion.comment_id),
                None,
            )
            result = await client.publish_reply(
                comment_id=suggestion.comment_id,
                reply_text=suggestion.reply_text,
                pin_url=pin_url,
            )
            _mark_reply_post_result(db, account_id=account_id, result=result)
            posted.append(result)

        return AutoReplyResult(
            account_id=account_id,
            dry_run=False,
            suggestions=suggestions,
            posted=posted,
        )
    finally:
        if owns_db:
            db.close()


def classify_comment_safety(text: str) -> tuple[str, str | None]:
    """Classify comment safety.

    Single-word English markers use ``\\b`` boundaries to avoid matching
    substrings (e.g. "price" should not flag "priceless").  Multi-word
    phrases and Chinese characters use plain substring matching.
    """
    import re

    normalized = text.lower()

    # Single-word markers with word-boundary matching
    word_markers = {
        "refund": "refund_or_order_issue",
        "return": "refund_or_order_issue",
        "chargeback": "refund_or_order_issue",
        "scam": "complaint",
        "complaint": "complaint",
        "stolen": "copyright_or_ip",
        "copyright": "copyright_or_ip",
        "trademark": "copyright_or_ip",
        "lawsuit": "legal",
        "sue": "legal",
        "price": "pricing_dispute",
        "password": "account_security",
    }
    for word, reason in word_markers.items():
        if re.search(rf"\b{re.escape(word)}\b", normalized):
            return "manual_review", reason

    # Multi-word phrases — low false-positive risk with plain substring
    phrase_markers = {
        "too expensive": "pricing_dispute",
        "account hacked": "account_security",
    }
    for phrase, reason in phrase_markers.items():
        if phrase in normalized:
            return "manual_review", reason

    # Chinese character markers
    cn_markers = {
        "退款": "refund_or_order_issue",
        "退货": "refund_or_order_issue",
        "投诉": "complaint",
        "侵权": "copyright_or_ip",
        "版权": "copyright_or_ip",
        "商标": "copyright_or_ip",
        "太贵": "pricing_dispute",
        "账号": "account_security",
    }
    for marker, reason in cn_markers.items():
        if marker in normalized:
            return "manual_review", reason

    return "safe", None


def _get_reply_record(db: Session, *, account_id: str, comment_id: str) -> ReplyRecord | None:
    return db.scalar(
        select(ReplyRecord).where(
            ReplyRecord.account_id == account_id,
            ReplyRecord.comment_id == comment_id,
        )
    )


def _upsert_reply_record(
    db: Session,
    *,
    comment: SocialComment,
    reply_text: str | None,
    status: str,
    safety_status: str,
    safety_reason: str | None,
) -> ReplyRecord:
    record = _get_reply_record(
        db,
        account_id=comment.account_id,
        comment_id=comment.comment_id,
    )
    raw: dict[str, Any] = {
        "pin_url": comment.pin_url,
        "author_name": comment.author_name,
    }
    if record is None:
        record = ReplyRecord(
            account_id=comment.account_id,
            comment_id=comment.comment_id,
            pin_url=comment.pin_url,
            author_name=comment.author_name,
            comment_text=comment.text,
            reply_text=reply_text,
            status=status,
            safety_status=safety_status,
            safety_reason=safety_reason,
            raw_json=raw,
        )
        db.add(record)
    else:
        record.pin_url = comment.pin_url
        record.author_name = comment.author_name
        record.comment_text = comment.text
        record.reply_text = reply_text
        record.status = status
        record.safety_status = safety_status
        record.safety_reason = safety_reason
        record.raw_json = raw
    db.commit()
    db.refresh(record)
    return record


def _mark_reply_post_result(db: Session, *, account_id: str, result: ReplyPostResult) -> None:
    record = _get_reply_record(db, account_id=account_id, comment_id=result.comment_id)
    if record is None:
        return
    record.status = "posted" if result.posted else "failed"
    record.posted_at = datetime.now(UTC) if result.posted else None
    record.raw_json = result.raw
    db.commit()


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
