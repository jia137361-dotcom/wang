from fastapi import FastAPI

from fastapi import Depends
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

app = FastAPI(
    title=settings.app_name,
    dependencies=[Depends(verify_api_key)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(automation.router, prefix="/api/automation", tags=["automation"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(evomap_stats.router, prefix="/api/evomap", tags=["evomap"])
app.include_router(planner.router, prefix="/api/planner", tags=["planner"])
app.include_router(publish.router, prefix="/api/publish", tags=["publish"])
app.include_router(publish_jobs.router, prefix="/api/publish-jobs", tags=["publish-jobs"])
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(token_usage.router, prefix="/api/token-usage", tags=["token-usage"])
app.include_router(trends.router, prefix="/api/trends", tags=["trends"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["uploads"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
