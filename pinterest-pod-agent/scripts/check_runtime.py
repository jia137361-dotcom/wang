from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_sessionmaker
from app.main import app
from app.models.campaign import Campaign
from app.models.global_strategy import GlobalStrategy
from app.models.publish_job import PublishJob
from app.models.social_account import SocialAccount


ACCOUNT_ID = "runtime_account_001"
CAMPAIGN_ID = "runtime_campaign_001"
STRATEGY_SCOPE = "runtime_scope"
IMAGE_PATH = Path("var/uploads/runtime_test.png")


def cleanup() -> None:
    with get_sessionmaker()() as db:
        db.execute(delete(PublishJob).where(PublishJob.account_id == ACCOUNT_ID))
        db.execute(delete(SocialAccount).where(SocialAccount.account_id == ACCOUNT_ID))
        db.execute(delete(Campaign).where(Campaign.campaign_id == CAMPAIGN_ID))
        db.execute(delete(GlobalStrategy).where(GlobalStrategy.scope == STRATEGY_SCOPE))
        db.commit()


def assert_ok(response, expected: int = 200):
    assert response.status_code == expected, f"{response.status_code}: {response.text}"
    return response.json() if response.text else None


if __name__ == "__main__":
    cleanup()
    IMAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Valid enough PNG signature for path existence validation; upload tests use multipart separately.
    IMAGE_PATH.write_bytes(b"\x89PNG\r\n\x1a\n")

    client = TestClient(app)
    print("health", assert_ok(client.get("/health")))
    print("analytics_summary", assert_ok(client.get("/api/analytics/summary")))
    print("scheduler", assert_ok(client.get("/api/scheduler/snapshot")))
    print("token_summary", assert_ok(client.get("/api/token-usage/summary")))

    account = assert_ok(
        client.post(
            "/api/accounts/",
            json={
                "account_id": ACCOUNT_ID,
                "display_name": "Runtime Account",
                "adspower_profile_id": "profile-runtime",
                "proxy_region": "US",
                "risk_status": "normal",
            },
        ),
        201,
    )
    print("account", account["account_id"])

    campaign = assert_ok(
        client.post(
            "/api/campaigns/",
            json={
                "campaign_id": CAMPAIGN_ID,
                "name": "Runtime Campaign",
                "niche": "pet lovers",
                "product_type": "t-shirt",
                "audience": "dog moms",
                "status": "active",
            },
        ),
        201,
    )
    print("campaign", campaign["campaign_id"])

    content_brief = assert_ok(client.post(f"/api/campaigns/{CAMPAIGN_ID}/content-brief"))
    assert "Pinterest POD" in content_brief["prompt"]
    print("campaign_content_brief_ok")

    trends = assert_ok(
        client.post(f"/api/trends/{STRATEGY_SCOPE}", json={"keywords": ["Dog Mom Shirt", "Custom Pet Gift"]})
    )
    assert trends["trend_keywords"] == ["custom pet gift", "dog mom shirt"]
    print("trends_ok")

    planner = assert_ok(client.get("/api/planner/daily"))
    assert planner["tasks"]
    print("planner_tasks", len(planner["tasks"]))

    job = assert_ok(
        client.post(
            "/api/publish-jobs/",
            json={
                "account_id": ACCOUNT_ID,
                "campaign_id": CAMPAIGN_ID,
                "board_name": "Pet Lovers",
                "image_path": str(IMAGE_PATH),
                "title": "Runtime Pin",
                "description": "Runtime description",
                "product_type": "t-shirt",
                "niche": "pet lovers",
                "audience": "dog moms",
            },
        ),
        201,
    )
    print("job", job["job_id"])
    prepared = assert_ok(client.post(f"/api/publish-jobs/{job['job_id']}/run"))
    assert prepared["dry_run"] is True
    print("job_run_prepare_ok")

    dry_run = assert_ok(
        client.post(
            "/api/publish/pins/adspower",
            json={
                "account_id": ACCOUNT_ID,
                "campaign_id": CAMPAIGN_ID,
                "board_name": "Pet Lovers",
                "image_path": str(IMAGE_PATH),
                "title": "Runtime Pin",
                "description": "Runtime description",
                "product_type": "t-shirt",
                "niche": "pet lovers",
                "audience": "dog moms",
                "dry_run": True,
            },
        )
    )
    assert dry_run["success"] is True
    print("publish_dry_run_ok")

    cleanup()
    IMAGE_PATH.unlink(missing_ok=True)
    print("runtime_check_ok")
