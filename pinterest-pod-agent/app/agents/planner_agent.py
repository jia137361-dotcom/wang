from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evomap.prompt_evolve import PromptContext
from app.models.campaign import Campaign
from app.models.social_account import SocialAccount


@dataclass(frozen=True)
class PlannedPinTask:
    account_id: str
    campaign_id: str
    product_type: str
    niche: str
    audience: str
    board_name: str
    prompt_context: PromptContext
    scheduled_at: datetime


class PlannerAgent:
    def __init__(self, db: Session) -> None:
        self.db = db

    def plan_daily_tasks(self, *, limit: int = 20) -> list[PlannedPinTask]:
        campaigns = self.db.scalars(
            select(Campaign)
            .where(Campaign.status.in_(["active", "draft"]))
            .order_by(Campaign.created_at.desc())
            .limit(limit)
        ).all()
        accounts = self.db.scalars(
            select(SocialAccount)
            .where(SocialAccount.platform == "pinterest")
            .where(SocialAccount.risk_status.in_(["unknown", "normal"]))
            .order_by(SocialAccount.created_at.asc())
            .limit(limit)
        ).all()
        if not campaigns or not accounts:
            return []

        tasks: list[PlannedPinTask] = []
        for index, campaign in enumerate(campaigns):
            account = accounts[index % len(accounts)]
            product_type = campaign.product_type or "pod product"
            niche = campaign.niche or "general gifts"
            audience = campaign.audience or "Pinterest shoppers"
            tasks.append(
                PlannedPinTask(
                    account_id=account.account_id,
                    campaign_id=campaign.campaign_id,
                    product_type=product_type,
                    niche=niche,
                    audience=audience,
                    board_name=niche.title(),
                    scheduled_at=datetime.now(UTC),
                    prompt_context=PromptContext(
                        product_type=product_type,
                        niche=niche,
                        audience=audience,
                        season=campaign.season,
                        offer=campaign.offer,
                        destination_url=campaign.destination_url,
                    ),
                )
            )
        return tasks
