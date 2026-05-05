"""Clear pending/ready/scheduled tasks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_sessionmaker
from app.models.scheduled_task import ScheduledTask
from sqlalchemy import delete

db = get_sessionmaker()()
try:
    count = db.query(ScheduledTask).filter(
        ScheduledTask.status.in_(["pending", "ready", "scheduled"])
    ).delete(synchronize_session=False)
    db.commit()
    print(f"Deleted {count} pending/ready/scheduled tasks")
finally:
    db.close()
