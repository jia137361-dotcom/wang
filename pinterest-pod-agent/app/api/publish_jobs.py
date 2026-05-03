from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.evomap.content_variant_generator import ContentVariantGenerator
from app.evomap.prompt_evolve import PromptContext
from app.models.publish_job import PublishJob
from app.schemas.publish import PublishRequest
from app.schemas.publish_jobs import (
    ContentGenerateRequest,
    ContentGenerateResponse,
    PublishJobCreate,
    PublishJobRead,
)


router = APIRouter()


@router.post("/generate-content", response_model=ContentGenerateResponse)
def generate_deduped_content(
    payload: ContentGenerateRequest, db: Session = Depends(get_db)
) -> ContentGenerateResponse:
    """Generate deduplicated content candidates via ContentVariantGenerator.

    Returns the first candidate that passes all dedup gates (history + batch)
    or a failure reason when all candidates are too similar to existing Pins.
    """
    context = PromptContext(
        product_type=payload.product_type,
        niche=payload.niche,
        audience=payload.audience,
        season=payload.season,
        offer=payload.offer,
        destination_url=payload.destination_url,
    )
    generator = ContentVariantGenerator(db=db)
    result = generator.select_best_candidate(
        context, account_id=payload.account_id
    )
    return ContentGenerateResponse(
        title=result.title,
        description=result.description,
        keywords=result.keywords,
        angle=result.angle,
        style_variant=result.style_variant,
        title_hash=result.title_hash,
        description_hash=result.description_hash,
        content_hash=result.content_hash,
        content_batch_id=result.content_batch_id,
        accepted=result.accepted,
        reason=result.reason,
    )


@router.post("/", response_model=PublishJobRead, status_code=status.HTTP_201_CREATED)
def create_publish_job(payload: PublishJobCreate, db: Session = Depends(get_db)) -> PublishJob:
    image_path = str(payload.image_path) if payload.image_path else "pending_auto_generation"
    data = payload.model_dump(exclude={"image_path"})
    data["title"] = data.get("title") or "pending_auto_generation"
    data["description"] = data.get("description") or "pending_auto_generation"
    job = PublishJob(
        job_id=f"job_{uuid4().hex[:16]}",
        image_path=image_path,
        **data,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/", response_model=list[PublishJobRead])
def list_publish_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    account_id: str | None = None,
    campaign_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[PublishJob]:
    stmt = select(PublishJob).order_by(PublishJob.created_at.desc()).offset(offset).limit(limit)
    if status_filter:
        stmt = stmt.where(PublishJob.status == status_filter)
    if account_id:
        stmt = stmt.where(PublishJob.account_id == account_id)
    if campaign_id:
        stmt = stmt.where(PublishJob.campaign_id == campaign_id)
    return list(db.scalars(stmt).all())


@router.get("/{job_id}", response_model=PublishJobRead)
def get_publish_job(job_id: str, db: Session = Depends(get_db)) -> PublishJob:
    job = _get_job(db, job_id)
    return job


@router.post("/{job_id}/run", response_model=PublishRequest)
def prepare_publish_job_run(job_id: str, db: Session = Depends(get_db)) -> PublishRequest:
    job = _get_job(db, job_id)
    if job.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is cancelled")

    job.status = "ready"
    job.started_at = datetime.now(UTC)
    db.commit()
    return PublishRequest(
        account_id=job.account_id,
        campaign_id=job.campaign_id,
        board_name=job.board_name,
        image_path=Path(job.image_path),
        title=job.title,
        description=job.description,
        destination_url=job.destination_url,
        product_type=job.product_type,
        niche=job.niche,
        audience=job.audience,
        season=job.season,
        offer=job.offer,
        dry_run=True,
    )


@router.post("/{job_id}/cancel", response_model=PublishJobRead)
def cancel_publish_job(job_id: str, db: Session = Depends(get_db)) -> PublishJob:
    job = _get_job(db, job_id)
    if job.status in {"published", "failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is already finished")
    job.status = "cancelled"
    job.finished_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def _get_job(db: Session, job_id: str) -> PublishJob:
    job = db.scalar(select(PublishJob).where(PublishJob.job_id == job_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publish job not found")
    return job
