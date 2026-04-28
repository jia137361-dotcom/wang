from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.agents.planner_agent import PlannerAgent
from app.database import get_db


router = APIRouter()


@router.get("/daily")
def daily_plan(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    planner = PlannerAgent(db)
    tasks = planner.plan_daily_tasks(limit=limit)
    return {
        "tasks": [
            {
                "account_id": task.account_id,
                "campaign_id": task.campaign_id,
                "product_type": task.product_type,
                "niche": task.niche,
                "audience": task.audience,
                "board_name": task.board_name,
                "scheduled_at": task.scheduled_at.isoformat(),
                "prompt_context": task.prompt_context.__dict__,
            }
            for task in tasks
        ]
    }
