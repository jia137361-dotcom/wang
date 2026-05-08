#!/usr/bin/env python3
"""Create a new publish_job and scheduled_task directly in database."""
import json, uuid, sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine, text
from app.config import get_settings

e = create_engine(get_settings().database_url)
with e.connect() as c:
    # Check for existing incomplete warmup_and_publish task for this account
    existing = c.execute(text("""
        SELECT task_id, status, created_at FROM scheduled_task
        WHERE account_id = 'test-account-1'
          AND task_type = 'warmup_and_publish'
          AND status IN ('pending', 'ready', 'running')
        ORDER BY created_at DESC
        LIMIT 1
    """)).fetchone()
    if existing:
        print(f"已存在未完成的 warmup_and_publish 任务: task_id={existing[0]} status={existing[1]} created_at={existing[2]}")
        print("请等待该任务完成/失败后再创建新任务，或手动取消它。")
        sys.exit(1)

    job_id = "job_demo_" + uuid.uuid4().hex[:8]
    st_id = "st_demo_" + uuid.uuid4().hex[:8]

    payload_json = json.dumps({
        "account_id": "test-account-1",
        "job_id": job_id,
        "warmup_duration_minutes": 5,
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
    print("PublishJob: " + job_id)

    c.execute(text("""
        INSERT INTO scheduled_task (task_id, task_type, platform, account_id, status, priority, scheduled_at, payload_json, created_at, updated_at)
        VALUES (:sid, 'warmup_and_publish', 'pinterest', 'test-account-1', 'pending', 10, NOW(),
            CAST(:payload AS jsonb), NOW(), NOW())
    """), {"sid": st_id, "payload": payload_json})
    c.commit()

print("ScheduledTask: " + st_id)
print("Demo setup done. Run the worker to start.")
