from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.prompt_evolve import PromptContext, PromptEvolver
from app.models.campaign import Campaign
from app.schemas.campaigns import CampaignCreate, CampaignRead, CampaignUpdate
from app.schemas.evomap import PromptBuildResponse


router = APIRouter()


@router.post("/", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)) -> Campaign:
    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Campaign already exists: {payload.campaign_id}",
        ) from exc
    db.refresh(campaign)
    return campaign


@router.get("/", response_model=list[CampaignRead])
def list_campaigns(
    status_filter: str | None = Query(default=None, alias="status"),
    niche: str | None = None,
    product_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Campaign]:
    stmt = select(Campaign).order_by(Campaign.created_at.desc()).offset(offset).limit(limit)
    if status_filter:
        stmt = stmt.where(Campaign.status == status_filter)
    if niche:
        stmt = stmt.where(Campaign.niche == niche)
    if product_type:
        stmt = stmt.where(Campaign.product_type == product_type)
    return list(db.scalars(stmt).all())


@router.get("/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)) -> Campaign:
    campaign = db.scalar(select(Campaign).where(Campaign.campaign_id == campaign_id))
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: str,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
) -> Campaign:
    campaign = db.scalar(select(Campaign).where(Campaign.campaign_id == campaign_id))
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: str, db: Session = Depends(get_db)) -> None:
    campaign = db.scalar(select(Campaign).where(Campaign.campaign_id == campaign_id))
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    db.delete(campaign)
    db.commit()


@router.post("/{campaign_id}/content-brief", response_model=PromptBuildResponse)
def campaign_content_brief(
    campaign_id: str,
    generate: bool = False,
    db: Session = Depends(get_db),
) -> PromptBuildResponse:
    campaign = _get_campaign_or_404(db, campaign_id)
    evolver = PromptEvolver(db=db)
    context = _campaign_context(campaign)
    prompt = evolver.build_content_prompt(context)
    generated_text = evolver.generate_content_brief(context) if generate else None
    return PromptBuildResponse(prompt=prompt, generated_text=generated_text)


@router.post("/{campaign_id}/visual-prompt", response_model=PromptBuildResponse)
def campaign_visual_prompt(
    campaign_id: str,
    generate: bool = False,
    db: Session = Depends(get_db),
) -> PromptBuildResponse:
    campaign = _get_campaign_or_404(db, campaign_id)
    evolver = PromptEvolver(db=db)
    context = _campaign_context(campaign)
    prompt = evolver.build_visual_prompt(context)
    generated_text = evolver.volc_client.generate_text(
        prompt,
        system_prompt="You are a Pinterest POD visual strategy expert.",
        temperature=0.6,
        max_tokens=1400,
    ) if generate else None
    return PromptBuildResponse(prompt=prompt, generated_text=generated_text)


def _get_campaign_or_404(db: Session, campaign_id: str) -> Campaign:
    campaign = db.scalar(select(Campaign).where(Campaign.campaign_id == campaign_id))
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")
    return campaign


def _campaign_context(campaign: Campaign) -> PromptContext:
    return PromptContext(
        product_type=campaign.product_type or "pod product",
        niche=campaign.niche or "general gifts",
        audience=campaign.audience or "Pinterest shoppers",
        season=campaign.season,
        offer=campaign.offer,
        destination_url=campaign.destination_url,
    )
