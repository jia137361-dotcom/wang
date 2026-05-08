"""Combined warmup-then-publish workflow -- single browser session.

Opens AdsPower once, runs a warmup browsing session, then immediately
publishes a Pin on the same page without re-logging in or refreshing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.automation.browser_factory import BrowserSession, open_adspower_profile
from app.automation.pinterest_flow import PinDraft, PinterestFlow, PublishResult
from app.evomap.prompt_evolve import PromptContext
from app.models.publish_job import PublishJob
from app.models.social_account import SocialAccount
from app.tools.adspower_api import AdsPowerClient
from app.workflows.pin_publish_flow import (
    AccountPublishWorkflowInput,
    record_publish,
)
from app.workflows.warmup_flow import WarmupResult, run_warmup_session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WarmupPublishResult:
    warmup: WarmupResult | None
    publish: PublishResult | None
    pin_performance_id: int | None = None


async def run_warmup_then_publish(
    *,
    account_id: str,
    job_id: str,
    warmup_duration_minutes: int | None = None,
    adspower_client: AdsPowerClient | None = None,
    content_batch_id: str | None = None,
) -> WarmupPublishResult:
    """Run warmup then publish in a single AdsPower browser session.

    The same ``Page`` is shared so Pinterest sees one continuous session.
    """
    from app.database import get_sessionmaker
    from app.models.account_policy import AccountPolicy
    from app.safety.proxy_check import verify_us_ip

    # resolve account & job
    with get_sessionmaker()() as db:
        account = db.scalar(
            select(SocialAccount).where(SocialAccount.account_id == account_id)
        )
        if account is None:
            raise ValueError(f"SocialAccount not found: {account_id}")
        if not account.adspower_profile_id:
            raise ValueError(f"Account has no AdsPower profile bound: {account_id}")
        profile_id = account.adspower_profile_id

        job = db.scalar(select(PublishJob).where(PublishJob.job_id == job_id))
        if job is None:
            raise ValueError(f"PublishJob not found: {job_id}")

        if warmup_duration_minutes is None:
            policy = db.scalar(
                select(AccountPolicy).where(AccountPolicy.account_id == account_id)
            )
            if policy and policy.warmup_duration_min:
                warmup_duration_minutes = policy.warmup_duration_min
            else:
                warmup_duration_minutes = 5

        # Truncate title and description to Pinterest limits before creating PinDraft
        truncated_title = job.title.strip()
        if len(truncated_title) > 100:
            logger.warning("Title truncated %d → 100 chars for job=%s", len(truncated_title), job_id)
            truncated_title = truncated_title[:100].strip()
        truncated_description = (job.description or "").strip()
        if len(truncated_description) > 800:
            logger.warning("Description truncated %d → 800 chars for job=%s", len(truncated_description), job_id)
            truncated_description = truncated_description[:800].strip()

        # Build workflow input while we have the DB session
        publish_input = AccountPublishWorkflowInput(
            account_id=job.account_id,
            campaign_id=job.campaign_id,
            board_name=job.board_name,
            image_path=Path(job.image_path),
            title=truncated_title,
            description=truncated_description,
            destination_url=job.destination_url,
            visual_prompt=None,
            prompt_context=PromptContext(
                product_type=job.product_type,
                niche=job.niche,
                audience=job.audience,
                season=job.season,
                offer=job.offer,
                destination_url=job.destination_url,
            ),
        )
        variant_angle = job.variant_angle
        content_hash = job.content_hash
        title_hash = job.title_hash
        description_hash = job.description_hash

    # single browser session for both warmup and publish
    session: BrowserSession | None = None
    try:
        session = await open_adspower_profile(profile_id, adspower_client=adspower_client)
        await verify_us_ip(session.page)

        # phase 1: warmup
        warmup_result = await run_warmup_session(
            session.page,
            account_id=account_id,
            duration_minutes=warmup_duration_minutes,
        )
        logger.info(
            "Warmup phase done account=%s elapsed=%ds",
            account_id,
            int(warmup_result.duration_seconds),
        )

        # phase 2: publish on the same page
        await session.page.goto("https://www.pinterest.com/", wait_until="domcontentloaded")
        pinterest = PinterestFlow(session.page)
        tagged_topics = None
        if job.tagged_topics:
            import json as _json
            try:
                tagged_topics = _json.loads(job.tagged_topics)
            except Exception:
                pass

        draft = PinDraft(
            title=truncated_title,
            description=truncated_description,
            board_name=job.board_name,
            image_path=Path(job.image_path),
            destination_url=job.destination_url or None,
            tagged_topics=tagged_topics,
        )
        publish_result = await pinterest.publish_pin(draft)

        # record to PinPerformance via EvoMap (non-fatal — don't fail the task)
        pin_perf_id: int | None = None
        try:
            with get_sessionmaker()() as db:
                from app.evomap.prompt_evolve import PromptEvolver

                evolver = PromptEvolver(db=db)
                content_prompt = evolver.build_content_prompt(publish_input.prompt_context)
                record = record_publish(
                    db=db,
                    evolver=evolver,
                    workflow_input=publish_input,
                    result=publish_result,
                    content_prompt=content_prompt,
                    content_batch_id=content_batch_id,
                    variant_angle=variant_angle,
                    content_hash=content_hash,
                    title_hash=title_hash,
                    description_hash=description_hash,
                )
                pin_perf_id = record.id
        except Exception:
            logger.exception("PinPerformance recording failed — publish is still successful")

        return WarmupPublishResult(
            warmup=warmup_result,
            publish=publish_result,
            pin_performance_id=pin_perf_id,
        )
    finally:
        if session is not None:
            await session.close()
