"""One-shot test: create task + dispatch."""
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.database import get_sessionmaker
from app.models.scheduled_task import ScheduledTask
from app.models.publish_job import PublishJob
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime, UTC
from app.jobs.dispatcher import dispatch_ready_tasks

db = get_sessionmaker()()
try:
    # Cancel all old running/pending tasks for this account
    stale = list(db.scalars(select(ScheduledTask).where(
        ScheduledTask.account_id == 'test-account-1',
        ScheduledTask.status.in_(['running', 'ready', 'scheduled', 'pending'])
    )).all())
    for t in stale:
        t.status = 'cancelled'
        print(f'Cancelled: {t.task_id}')

    # Reset publish job to ready
    job = db.scalar(select(PublishJob).where(PublishJob.job_id == 'job_8f48ec68f3ee4b45'))
    if job and job.status != 'ready':
        old = job.status
        job.status = 'ready'
        print(f'Job status: {old} → ready')

    db.commit()

    # Create new task
    task = ScheduledTask(
        task_id=f'st_{uuid4().hex[:16]}',
        task_type='warmup_and_publish',
        account_id='test-account-1',
        status='pending',
        priority=5,
        scheduled_at=datetime.now(UTC),
        payload_json={
            'account_id': 'test-account-1',
            'job_id': 'job_8f48ec68f3ee4b45',
            'warmup_duration_minutes': 10,
            'dry_run': False,
        },
    )
    db.add(task)
    db.commit()
    print(f'Task created: {task.task_id}')

    # Dispatch
    result = dispatch_ready_tasks(db, limit=20, dry_run=False)
    db.commit()
    print(f'Dispatched: {result["dispatched"]} | skipped: {result["skipped"]}')
finally:
    db.close()
