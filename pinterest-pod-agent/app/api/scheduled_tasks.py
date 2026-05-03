"""CRUD endpoints for ScheduledTask — the unified task queue."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account_policy import AccountPolicy
from app.models.scheduled_task import ScheduledTask, TASK_TYPES

router = APIRouter()


# ---------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------


class ScheduledTaskCreate(BaseModel):
    task_type: str = Field(max_length=40)
    platform: str = Field(default="pinterest", max_length=40)
    account_id: str | None = Field(default=None, max_length=64)
    campaign_id: str | None = Field(default=None, max_length=64)
    priority: int = Field(default=0, ge=0, le=10)
    scheduled_at: datetime | None = None
    max_attempts: int = Field(default=3, ge=1, le=10)
    payload_json: dict = Field(default_factory=dict)


class ScheduledTaskRead(BaseModel):
    task_id: str
    task_type: str
    platform: str
    account_id: str | None = None
    campaign_id: str | None = None
    status: str
    priority: int
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    attempt_count: int
    max_attempts: int
    error_message: str | None = None
    error_type: str | None = None
    payload_json: dict
    result_json: dict
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScheduledTaskList(BaseModel):
    items: list[ScheduledTaskRead]
    total: int


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@router.post("/", response_model=ScheduledTaskRead, status_code=status.HTTP_201_CREATED)
def create_scheduled_task(payload: ScheduledTaskCreate, db: Session = Depends(get_db)) -> ScheduledTask:
    if payload.task_type not in TASK_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown task_type. Allowed: {sorted(TASK_TYPES)}",
        )
    task = ScheduledTask(
        task_id=f"st_{uuid4().hex[:16]}",
        scheduled_at=payload.scheduled_at or datetime.now(UTC),
        **payload.model_dump(exclude={"scheduled_at"}),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/", response_model=ScheduledTaskList)
def list_scheduled_tasks(
    task_type: str | None = Query(default=None),
    account_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(ScheduledTask).order_by(ScheduledTask.scheduled_at.desc())
    count_stmt = select(func.count(ScheduledTask.id))

    if task_type:
        stmt = stmt.where(ScheduledTask.task_type == task_type)
        count_stmt = count_stmt.where(ScheduledTask.task_type == task_type)
    if account_id:
        stmt = stmt.where(ScheduledTask.account_id == account_id)
        count_stmt = count_stmt.where(ScheduledTask.account_id == account_id)
    if status:
        stmt = stmt.where(ScheduledTask.status == status)
        count_stmt = count_stmt.where(ScheduledTask.status == status)

    total = db.scalar(count_stmt) or 0
    items = list(db.scalars(stmt.offset(offset).limit(limit)).all())
    return {"items": items, "total": total}


@router.get("/{task_id}", response_model=ScheduledTaskRead)
def get_scheduled_task(task_id: str, db: Session = Depends(get_db)) -> ScheduledTask:
    task = db.scalar(select(ScheduledTask).where(ScheduledTask.task_id == task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("/{task_id}/cancel", response_model=ScheduledTaskRead)
def cancel_scheduled_task(task_id: str, db: Session = Depends(get_db)) -> ScheduledTask:
    task = db.scalar(select(ScheduledTask).where(ScheduledTask.task_id == task_id))
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status in {"completed", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Task is already finished"
        )
    task.status = "cancelled"
    task.finished_at = datetime.now(UTC)
    db.commit()
    db.refresh(task)
    return task
