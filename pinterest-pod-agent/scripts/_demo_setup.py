"""One-shot: create a demo warmup_and_publish task.

This is a local debugging helper. It only cancels prior demo-prefixed rows and
must not be used as the normal production scheduler entry point.
"""
import json, uuid, sys
sys.path.insert(0, ".")

import redis
from sqlalchemy import create_engine, text

from app.config import get_settings

r = redis.from_url("redis://localhost:6379/0")
for k in r.keys("nanobot:lock:*"):
    r.delete(k)
print("Redis locks cleared")

e = create_engine(get_settings().database_url)
with e.connect() as c:
    c.execute(text("""
        UPDATE scheduled_task
        SET status='cancelled', finished_at=NOW()
        WHERE task_id LIKE 'st_demo_%'
          AND status IN ('pending','ready','scheduled','running')
    """))
    c.execute(text("""
        UPDATE publish_job
        SET status='cancelled', finished_at=NOW()
        WHERE job_id LIKE 'job_demo_%'
          AND status IN ('pending','ready','running')
    """))
    c.commit()
    print("Old demo tasks/jobs cancelled")

    job_id = "job_demo_" + uuid.uuid4().hex[:8]
    st_id = "st_demo_" + uuid.uuid4().hex[:8]

    payload_json = json.dumps({
        "account_id": "test-account-1",
        "job_id": job_id,
        "warmup_duration_minutes": 8,
    })

    c.execute(text("""
        INSERT INTO publish_job (job_id, account_id, campaign_id, board_name, title, description,
            destination_url, image_path, content_hash, title_hash, description_hash,
            tagged_topics, product_type, niche, audience, season, offer, status, created_at, updated_at)
        VALUES (:jid, 'test-account-1', 'demo', 'Spring Motivation',
            'pending_auto_generation',
            'pending_auto_generation',
            NULL,
            'pending_auto_generation',
            NULL, NULL, NULL,
            '["Motivation","Poster Art","Home Office Decor"]',
            'poster', 'young professionals', 'ambitious career starters', 'spring', 'free shipping',
            'pending', NOW(), NOW())
    """), {"jid": job_id})
    print(f"PublishJob: {job_id}")

    c.execute(text("""
        INSERT INTO scheduled_task (task_id, task_type, platform, account_id, status, priority, scheduled_at, payload_json, created_at, updated_at)
        VALUES (:sid, 'warmup_and_publish', 'pinterest', 'test-account-1', 'pending', 10, NOW(),
            CAST(:payload AS jsonb), NOW(), NOW())
    """), {"sid": st_id, "payload": payload_json})
    c.commit()

print(f"ScheduledTask: {st_id}")
print("Demo setup done. Run the worker to start.")
