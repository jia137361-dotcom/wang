from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


ACCOUNT_ID = "test-account-1"
CAMPAIGN_ID = "pet-pod-campaign-001"
IMAGE_PATH = Path("var/uploads/pet_pinterest_post.png")


if __name__ == "__main__":
    client = TestClient(app)

    campaign_payload = {
        "campaign_id": CAMPAIGN_ID,
        "name": "Pet POD Gift Test",
        "niche": "pet lovers",
        "product_type": "poster",
        "audience": "dog moms, cat dads, and pet gift shoppers",
        "season": "evergreen",
        "offer": "personalized pet gift ideas",
        "destination_url": "https://example.com/pet-gifts",
        "status": "active",
    }
    response = client.post("/api/campaigns/", json=campaign_payload)
    if response.status_code == 409:
        response = client.patch(f"/api/campaigns/{CAMPAIGN_ID}", json=campaign_payload)
    assert response.status_code in {200, 201}, response.text

    dry_run_payload = {
        "account_id": ACCOUNT_ID,
        "campaign_id": CAMPAIGN_ID,
        "board_name": "Pet Lovers",
        "image_path": str(IMAGE_PATH),
        "title": "Custom Pet Gift Ideas for Pet Lovers",
        "description": "Discover personalized pet gift ideas for dog moms, cat dads, and animal lovers. This cozy custom pet design is made for Pinterest shoppers looking for thoughtful POD decor and everyday pet-inspired style.",
        "destination_url": "https://example.com/pet-gifts",
        "product_type": "poster",
        "niche": "pet lovers",
        "audience": "dog moms, cat dads, and pet gift shoppers",
        "season": "evergreen",
        "offer": "personalized pet gift ideas",
        "dry_run": True,
    }
    response = client.post("/api/publish/pins/adspower", json=dry_run_payload)
    assert response.status_code == 200, response.text
    print(response.json()["message"])
