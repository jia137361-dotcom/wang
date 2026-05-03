"""add scheduled_task and account_policy tables

Revision ID: 0003_scheduled_task
Revises: 0002_content_dedup
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0003_scheduled_task"
down_revision = "0002_content_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- scheduled_task ---
    op.create_table(
        "scheduled_task",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("task_type", sa.String(40), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False, server_default="pinterest"),
        sa.Column("account_id", sa.String(64), nullable=True),
        sa.Column("campaign_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(64), nullable=True),
        sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("celery_task_id", sa.String(128), nullable=True),
        sa.Column("payload_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("result_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("ix_scheduled_task_task_id", "scheduled_task", ["task_id"])
    op.create_index("ix_st_status_scheduled", "scheduled_task", ["status", "scheduled_at"])
    op.create_index("ix_st_account_status", "scheduled_task", ["account_id", "status"])
    op.create_index("ix_st_locked_by", "scheduled_task", ["locked_by"])
    op.create_index("ix_scheduled_task_task_type", "scheduled_task", ["task_type"])
    op.create_index("ix_scheduled_task_campaign_id", "scheduled_task", ["campaign_id"])

    # --- account_policy ---
    op.create_table(
        "account_policy",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("platform", sa.String(40), nullable=False, server_default="pinterest"),
        sa.Column("daily_max_posts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("min_post_interval_min", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("allowed_timezone_start", sa.String(5), nullable=True, server_default="09:00"),
        sa.Column("allowed_timezone_end", sa.String(5), nullable=True, server_default="22:00"),
        sa.Column("auto_reply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("warmup_sessions_per_day", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("warmup_duration_min", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
    )
    op.create_index("ix_account_policy_account_id", "account_policy", ["account_id"])


def downgrade() -> None:
    op.drop_table("account_policy")
    op.drop_table("scheduled_task")
