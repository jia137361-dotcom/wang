from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.jobs.tasks import (
    auto_reply_task,
    dispatch_publish_jobs_task,
    generate_image_asset_task,
    generate_image_for_publish_job_task,
    generate_marketing_video_task,
    publish_job_task,
    refresh_current_event_trends_task,
    refresh_product_trends_task,
)


router = APIRouter()


class TaskEnqueueResponse(BaseModel):
    task_id: str | None
    task_name: str
    status: str = "queued"


class ImageGenerateTaskRequest(BaseModel):
    prompt: str = Field(min_length=1)
    image_size: str = "portrait_16_9"
    publish_job_id: str | None = Field(default=None, max_length=64)


class PublishJobTaskRequest(BaseModel):
    dry_run: bool = False


class DispatchPublishJobsRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)
    dry_run: bool = True


class CurrentEventTrendTaskRequest(BaseModel):
    scope: str = Field(min_length=1, max_length=120)
    query: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ProductTrendTaskRequest(BaseModel):
    scope: str = Field(min_length=1, max_length=120)
    niche: str | None = None
    product_type: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class VideoGenerateTaskRequest(BaseModel):
    prompt: str = Field(min_length=1)
    image_url: str | None = None
    duration_seconds: int = Field(default=5, ge=1, le=30)
    aspect_ratio: str = "9:16"


class AutoReplyTaskRequest(BaseModel):
    account_id: str = Field(min_length=1, max_length=64)
    dry_run: bool = True
    limit: int = Field(default=20, ge=1, le=100)
    brand_voice: str | None = Field(default=None, max_length=240)


@router.post("/images/generate-task", response_model=TaskEnqueueResponse)
def enqueue_image_generation(payload: ImageGenerateTaskRequest) -> TaskEnqueueResponse:
    if payload.publish_job_id:
        return _enqueue(
            generate_image_for_publish_job_task,
            payload.publish_job_id,
            payload.prompt,
            payload.image_size,
        )
    return _enqueue(generate_image_asset_task, payload.prompt, payload.image_size)


@router.post("/publish-jobs/{job_id}/run-task", response_model=TaskEnqueueResponse)
def enqueue_publish_job(job_id: str, payload: PublishJobTaskRequest) -> TaskEnqueueResponse:
    return _enqueue(publish_job_task, job_id, dry_run=payload.dry_run)


@router.post("/publish-jobs/dispatch-task", response_model=TaskEnqueueResponse)
def enqueue_dispatch_publish_jobs(payload: DispatchPublishJobsRequest) -> TaskEnqueueResponse:
    return _enqueue(dispatch_publish_jobs_task, payload.limit, dry_run=payload.dry_run)


@router.post("/trends/current-events-task", response_model=TaskEnqueueResponse)
def enqueue_current_event_trends(payload: CurrentEventTrendTaskRequest) -> TaskEnqueueResponse:
    return _enqueue(refresh_current_event_trends_task, payload.scope, payload.query, payload.limit)


@router.post("/trends/products-task", response_model=TaskEnqueueResponse)
def enqueue_product_trends(payload: ProductTrendTaskRequest) -> TaskEnqueueResponse:
    return _enqueue(
        refresh_product_trends_task,
        payload.scope,
        payload.niche,
        payload.product_type,
        payload.limit,
    )


@router.post("/videos/generate-task", response_model=TaskEnqueueResponse)
def enqueue_video_generation(payload: VideoGenerateTaskRequest) -> TaskEnqueueResponse:
    return _enqueue(
        generate_marketing_video_task,
        payload.prompt,
        payload.image_url,
        payload.duration_seconds,
        payload.aspect_ratio,
    )


@router.post("/replies/auto-reply-task", response_model=TaskEnqueueResponse)
def enqueue_auto_reply(payload: AutoReplyTaskRequest) -> TaskEnqueueResponse:
    return _enqueue(
        auto_reply_task,
        payload.account_id,
        dry_run=payload.dry_run,
        limit=payload.limit,
        brand_voice=payload.brand_voice,
    )


def _enqueue(task: Any, *args: Any, **kwargs: Any) -> TaskEnqueueResponse:
    try:
        async_result = task.delay(*args, **kwargs)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return TaskEnqueueResponse(
        task_id=getattr(async_result, "id", None),
        task_name=getattr(task, "name", getattr(task, "__name__", "unknown")),
    )
