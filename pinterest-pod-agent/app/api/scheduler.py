from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.jobs.scheduler import mark_next_publish_job_ready, scheduler_snapshot


router = APIRouter()


@router.get("/snapshot")
def get_scheduler_snapshot(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    snapshot = scheduler_snapshot(
        db,
        enabled=settings.scheduler_enabled,
        interval_minutes=settings.publish_interval_minutes,
    )
    return {
        "enabled": snapshot.enabled,
        "pending_publish_jobs": snapshot.pending_publish_jobs,
        "next_publish_check_at": snapshot.next_publish_check_at.isoformat()
        if snapshot.next_publish_check_at
        else None,
    }


@router.post("/publish-jobs/mark-next-ready")
def mark_next_ready(db: Session = Depends(get_db)) -> dict:
    job = mark_next_publish_job_ready(db)
    return {"job_id": job.job_id if job else None, "status": job.status if job else "none"}
