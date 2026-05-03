from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    accounts,
    analytics,
    automation,
    campaigns,
    evomap_stats,
    planner,
    publish,
    publish_jobs,
    scheduled_tasks,
    scheduler,
    strategies,
    token_usage,
    trends,
    uploads,
)
from app.api.auth import verify_api_key
from app.config import get_settings
from app.logging_config import setup_logging


setup_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(dependencies=[Depends(verify_api_key)])
api_router.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
api_router.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
api_router.include_router(automation.router, prefix="/api/automation", tags=["automation"])
api_router.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
api_router.include_router(evomap_stats.router, prefix="/api/evomap", tags=["evomap"])
api_router.include_router(planner.router, prefix="/api/planner", tags=["planner"])
api_router.include_router(publish.router, prefix="/api/publish", tags=["publish"])
api_router.include_router(publish_jobs.router, prefix="/api/publish-jobs", tags=["publish-jobs"])
api_router.include_router(scheduled_tasks.router, prefix="/api/scheduled-tasks", tags=["scheduled-tasks"])
api_router.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])
api_router.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
api_router.include_router(token_usage.router, prefix="/api/token-usage", tags=["token-usage"])
api_router.include_router(trends.router, prefix="/api/trends", tags=["trends"])
api_router.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])

app.include_router(api_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
