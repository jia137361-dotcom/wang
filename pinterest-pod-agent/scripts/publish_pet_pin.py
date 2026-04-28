import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import get_sessionmaker
from app.evomap.prompt_evolve import PromptContext
from app.workflows.pin_publish_flow import AccountPublishWorkflowInput, run_pin_publish_with_adspower


async def main() -> None:
    db = get_sessionmaker()()
    try:
        result = await run_pin_publish_with_adspower(
            db=db,
            workflow_input=AccountPublishWorkflowInput(
                account_id="test-account-1",
                campaign_id="pet-pod-campaign-001",
                board_name="Pet Lovers",
                image_path=Path("var/uploads/pet_pinterest_post.png"),
                title="Custom Pet Gift Ideas for Pet Lovers",
                description=(
                    "Discover personalized pet gift ideas for dog moms, cat dads, "
                    "and animal lovers. This cozy custom pet design is made for "
                    "Pinterest shoppers looking for thoughtful POD decor and everyday "
                    "pet-inspired style."
                ),
                destination_url="https://example.com/pet-gifts",
                prompt_context=PromptContext(
                    product_type="poster",
                    niche="pet lovers",
                    audience="dog moms, cat dads, and pet gift shoppers",
                    season="evergreen",
                    offer="personalized pet gift ideas",
                    destination_url="https://example.com/pet-gifts",
                ),
            ),
        )
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
