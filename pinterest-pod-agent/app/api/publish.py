from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.prompt_evolve import PromptContext, PromptEvolver
from app.models.campaign import Campaign
from app.models.social_account import SocialAccount
from app.schemas.publish import PublishRequest, PublishResponse
from app.tools.adspower_api import AdsPowerError
from app.workflows.pin_publish_flow import AccountPublishWorkflowInput, run_pin_publish_with_adspower


router = APIRouter()


@router.post("/pins/adspower", response_model=PublishResponse)
async def publish_pin_with_adspower(
    payload: PublishRequest,
    db: Session = Depends(get_db),
) -> PublishResponse:
    _validate_publish_payload(payload, db)
    context = _prompt_context(payload)
    evolver = PromptEvolver(db=db)
    content_prompt = evolver.build_content_prompt(context)
    visual_prompt = evolver.build_visual_prompt(context)
    signals = evolver.get_keyword_signals(niche=payload.niche, product_type=payload.product_type)
    strategy_snapshot = {
        "source": "evomap_prompt_evolve",
        "keyword_signals": [signal.model_dump() for signal in signals],
    }

    if payload.dry_run:
        return PublishResponse(
            success=True,
            message="Dry run passed; no browser action was performed",
            content_prompt=content_prompt,
            visual_prompt=visual_prompt,
            strategy_snapshot=strategy_snapshot,
        )

    try:
        result = await run_pin_publish_with_adspower(
            db=db,
            workflow_input=AccountPublishWorkflowInput(
                account_id=payload.account_id,
                campaign_id=payload.campaign_id,
                board_name=payload.board_name,
                image_path=payload.image_path,
                title=payload.title,
                description=payload.description,
                destination_url=payload.destination_url,
                prompt_context=context,
                visual_prompt=visual_prompt,
            ),
        )
        return PublishResponse(
            success=result.success,
            message=result.message,
            pin_url=result.pin_url,
            pin_performance_id=result.pin_performance_id,
            content_prompt=content_prompt,
            visual_prompt=visual_prompt,
            strategy_snapshot=strategy_snapshot,
            debug_artifact_dir=result.debug_artifact_dir,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AdsPowerError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


def _validate_publish_payload(payload: PublishRequest, db: Session) -> None:
    account = db.scalar(select(SocialAccount).where(SocialAccount.account_id == payload.account_id))
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if payload.campaign_id:
        campaign = db.scalar(select(Campaign).where(Campaign.campaign_id == payload.campaign_id))
        if campaign is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")


def _prompt_context(payload: PublishRequest) -> PromptContext:
    return PromptContext(
        product_type=payload.product_type,
        niche=payload.niche,
        audience=payload.audience,
        season=payload.season,
        offer=payload.offer,
        destination_url=payload.destination_url,
    )
