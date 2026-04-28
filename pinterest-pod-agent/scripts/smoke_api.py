import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_sessionmaker
from app.main import app
from app.models.campaign import Campaign
from app.models.global_strategy import GlobalStrategy
from app.models.pin_performance import PinPerformance
from app.models.social_account import SocialAccount


ACCOUNT_ID = "smoke_account_001"
CAMPAIGN_ID = "smoke_campaign_001"
STRATEGY_SCOPE = "smoke_scope"
PIN_TITLE = "Smoke Pin"


def cleanup() -> None:
    with get_sessionmaker()() as db:
        db.execute(delete(SocialAccount).where(SocialAccount.account_id == ACCOUNT_ID))
        db.execute(delete(Campaign).where(Campaign.campaign_id == CAMPAIGN_ID))
        db.execute(delete(GlobalStrategy).where(GlobalStrategy.scope == STRATEGY_SCOPE))
        db.execute(delete(PinPerformance).where(PinPerformance.title == PIN_TITLE))
        db.commit()


if __name__ == "__main__":
    cleanup()
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}

    account = client.post(
        "/api/accounts/",
        json={
            "account_id": ACCOUNT_ID,
            "platform": "pinterest",
            "display_name": "Smoke Account",
            "adspower_profile_id": "profile-smoke",
            "proxy_region": "US",
        },
    )
    assert account.status_code == 201, account.text
    assert account.json()["account_id"] == ACCOUNT_ID

    account_patch = client.patch(
        f"/api/accounts/{ACCOUNT_ID}",
        json={"risk_status": "normal"},
    )
    assert account_patch.status_code == 200, account_patch.text
    assert account_patch.json()["risk_status"] == "normal"

    campaign = client.post(
        "/api/campaigns/",
        json={
            "campaign_id": CAMPAIGN_ID,
            "name": "Smoke Mother's Day Pets",
            "niche": "pet lovers",
            "product_type": "t-shirt",
            "audience": "women who buy custom dog gifts",
            "season": "Mother's Day",
            "offer": "15% off",
            "destination_url": "https://example.com/products/dog-mom-shirt",
        },
    )
    assert campaign.status_code == 201, campaign.text
    assert campaign.json()["campaign_id"] == CAMPAIGN_ID

    strategy = client.put(
        f"/api/strategies/{STRATEGY_SCOPE}",
        json={"strategy": {"keywords": ["dog mom shirt"]}, "version": "smoke"},
    )
    assert strategy.status_code == 200, strategy.text
    assert strategy.json()["strategy"]["keywords"] == ["dog mom shirt"]

    assert client.get("/api/analytics/summary").status_code == 200
    assert client.get("/api/evomap/keyword-signals").status_code == 200

    with get_sessionmaker()() as db:
        pin = PinPerformance(
            account_id=ACCOUNT_ID,
            campaign_id=CAMPAIGN_ID,
            product_type="t-shirt",
            niche="pet lovers",
            title=PIN_TITLE,
            description="Smoke description",
            content_prompt="Smoke content prompt",
            keywords=["dog mom shirt", "custom pet gift"],
        )
        db.add(pin)
        db.commit()
        db.refresh(pin)
        pin_id = pin.id

    metrics = client.post(
        f"/api/analytics/pins/{pin_id}/metrics",
        json={"impressions": 1000, "clicks": 50, "saves": 20, "comments": 3, "reactions": 7},
    )
    assert metrics.status_code == 200, metrics.text
    assert metrics.json()["ctr"] == 0.05

    signals = client.get("/api/evomap/keyword-signals", params={"niche": "pet lovers"})
    assert signals.status_code == 200, signals.text

    assert client.delete(f"/api/accounts/{ACCOUNT_ID}").status_code == 204
    assert client.delete(f"/api/campaigns/{CAMPAIGN_ID}").status_code == 204
    cleanup()
    print("smoke_api_ok")
