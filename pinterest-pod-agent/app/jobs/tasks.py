from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.celery_app import celery_app, run_async
from app.database import get_sessionmaker
from app.evomap.prompt_evolve import PromptContext
from app.models.publish_job import PublishJob
from app.workflows.auto_reply_flow import run_auto_reply_flow
from app.workflows.image_generation_flow import generate_image_asset
from app.workflows.pin_publish_flow import AccountPublishWorkflowInput, run_pin_publish_with_adspower
from app.workflows.trend_tracking_flow import refresh_current_event_trends, refresh_product_trends
from app.workflows.video_generation_flow import VideoGenerationInput, generate_marketing_video


@celery_app.task(name="app.jobs.generate_image_asset")
def generate_image_asset_task(prompt: str, image_size: str = "portrait_16_9") -> dict[str, Any]:
    asset = run_async(generate_image_asset(prompt=prompt, image_size=image_size))
    return asdict(asset)


@celery_app.task(name="app.jobs.generate_image_for_publish_job")
def generate_image_for_publish_job_task(
    job_id: str,
    prompt: str,
    image_size: str = "portrait_16_9",
) -> dict[str, Any]:
    asset = run_async(generate_image_asset(prompt=prompt, image_size=image_size))
    with get_sessionmaker()() as db:
        job = _get_publish_job(db, job_id)
        job.image_path = asset.local_path
        job.status = "pending"
        job.error_message = None
        db.commit()
    return asdict(asset) | {"job_id": job_id}


@celery_app.task(name="app.jobs.publish_job")
def publish_job_task(
    job_id: str, dry_run: bool = False, content_batch_id: str | None = None
) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        job = _get_publish_job(db, job_id)
        if job.status == "cancelled":
            raise RuntimeError(f"Publish job is cancelled: {job_id}")
        if not Path(job.image_path).exists():
            job.status = "failed"
            job.error_message = "Image path does not exist"
            job.finished_at = datetime.now(UTC)
            db.commit()
            raise FileNotFoundError(job.error_message)

        # use existing content hash fields if populated by ContentVariantGenerator
        batch_id = content_batch_id or job.content_batch_id or f"batch_{job_id[:12]}"
        job.content_batch_id = batch_id
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.error_message = None
        db.commit()

        if dry_run:
            job.status = "pending"
            db.commit()
            return {"job_id": job_id, "status": job.status, "dry_run": True}

        try:
            result = run_async(
                run_pin_publish_with_adspower(
                    db=db,
                    workflow_input=AccountPublishWorkflowInput(
                        account_id=job.account_id,
                        campaign_id=job.campaign_id,
                        board_name=job.board_name,
                        image_path=Path(job.image_path),
                        title=job.title,
                        description=job.description,
                        destination_url=job.destination_url,
                        prompt_context=PromptContext(
                            product_type=job.product_type,
                            niche=job.niche,
                            audience=job.audience,
                            season=job.season,
                            offer=job.offer,
                            destination_url=job.destination_url,
                        ),
                    ),
                    content_batch_id=batch_id,
                    variant_angle=job.variant_angle,
                    content_hash=job.content_hash,
                    title_hash=job.title_hash,
                    description_hash=job.description_hash,
                )
            )
            job.status = "published" if result.success else "failed"
            job.pin_performance_id = result.pin_performance_id
            job.error_message = None if result.success else result.message
            job.finished_at = datetime.now(UTC)
            db.commit()
            return {
                "job_id": job_id,
                "status": job.status,
                "pin_url": result.pin_url,
                "pin_performance_id": result.pin_performance_id,
                "debug_artifact_dir": result.debug_artifact_dir,
            }
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)
            db.commit()
            raise


@celery_app.task(name="app.jobs.dispatch_publish_jobs")
def dispatch_publish_jobs_task(limit: int = 10, dry_run: bool = True) -> dict[str, Any]:
    """Dispatch pending/ready publish jobs to Celery workers.

    dry_run is on by default to prevent accidental real-platform publishing
    during local development; pass False in production.
    """
    from uuid import uuid4

    batch_id = uuid4().hex[:16]
    celery_task_ids: list[str | None] = []
    with get_sessionmaker()() as db:
        jobs = list(
            db.scalars(
                select(PublishJob)
                .where(PublishJob.status.in_(["pending", "ready"]))
                .order_by(PublishJob.created_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        for job in jobs:
            if job.status == "pending":
                job.status = "ready"
        db.commit()

    for job in jobs:
        async_result = publish_job_task.delay(
            job.job_id, dry_run=dry_run, content_batch_id=batch_id
        )
        celery_task_ids.append(getattr(async_result, "id", None))

    return {"dispatched": len(jobs), "task_ids": celery_task_ids, "dry_run": dry_run, "batch_id": batch_id}


@celery_app.task(name="app.jobs.refresh_current_event_trends")
def refresh_current_event_trends_task(scope: str, query: str | None = None, limit: int = 20) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        return run_async(refresh_current_event_trends(db, scope=scope, query=query, limit=limit))


@celery_app.task(name="app.jobs.refresh_product_trends")
def refresh_product_trends_task(
    scope: str,
    niche: str | None = None,
    product_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    with get_sessionmaker()() as db:
        return run_async(
            refresh_product_trends(
                db,
                scope=scope,
                niche=niche,
                product_type=product_type,
                limit=limit,
            )
        )


@celery_app.task(name="app.jobs.generate_marketing_video")
def generate_marketing_video_task(
    prompt: str,
    image_url: str | None = None,
    duration_seconds: int = 5,
    aspect_ratio: str = "9:16",
) -> dict[str, Any]:
    video = run_async(
        generate_marketing_video(
            VideoGenerationInput(
                prompt=prompt,
                image_url=image_url,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
            )
        )
    )
    return asdict(video)


@celery_app.task(name="app.jobs.auto_reply")
def auto_reply_task(
    account_id: str,
    dry_run: bool = True,
    limit: int = 20,
    brand_voice: str | None = None,
) -> dict[str, Any]:
    result = run_async(
        run_auto_reply_flow(
            account_id=account_id,
            dry_run=dry_run,
            limit=limit,
            brand_voice=brand_voice,
        )
    )
    return {
        "account_id": result.account_id,
        "dry_run": result.dry_run,
        "suggestions": [asdict(item) for item in result.suggestions],
        "posted": [asdict(item) for item in result.posted],
    }


def _get_publish_job(db: Any, job_id: str) -> PublishJob:
    job = db.scalar(select(PublishJob).where(PublishJob.job_id == job_id))
    if job is None:
        raise ValueError(f"Publish job not found: {job_id}")
    return job
