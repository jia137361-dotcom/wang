from __future__ import annotations

from dataclasses import dataclass

from app.tools.reply_client import PinterestReplyClient, ReplyPostResult, SocialComment


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
    dry_run: bool = True,
    limit: int = 20,
    brand_voice: str | None = None,
) -> AutoReplyResult:
    """自动回复入口。

    当前只处理公司自有账号评论。平台读取/发回复逻辑留在
    PinterestReplyClient 中，等合规数据源和权限确认后再填。
    """
    client = PinterestReplyClient()
    comments = await client.fetch_unreplied_comments(account_id=account_id, limit=limit)
    suggestions = [
        ReplySuggestion(
            comment_id=comment.comment_id,
            comment_text=comment.text,
            reply_text=_build_reply_text(comment, brand_voice=brand_voice),
            posted=False,
        )
        for comment in comments
    ]

    if dry_run:
        return AutoReplyResult(account_id=account_id, dry_run=True, suggestions=suggestions, posted=[])

    posted: list[ReplyPostResult] = []
    for suggestion in suggestions:
        posted.append(
            await client.publish_reply(
                comment_id=suggestion.comment_id,
                reply_text=suggestion.reply_text,
            )
        )
    return AutoReplyResult(account_id=account_id, dry_run=False, suggestions=suggestions, posted=posted)


def _build_reply_text(comment: SocialComment, *, brand_voice: str | None) -> str:
    voice = f" {brand_voice.strip()}" if brand_voice and brand_voice.strip() else ""
    if "?" in comment.text:
        return f"Thanks for asking.{voice} We will check this and get back with the right details."
    return f"Thanks for your comment.{voice} We appreciate the feedback."
