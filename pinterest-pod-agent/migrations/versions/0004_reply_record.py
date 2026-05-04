"""add reply record table

Revision ID: 0004_reply_record
Revises: 0003_scheduled_task
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0004_reply_record"
down_revision = "0003_scheduled_task"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reply_record",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("comment_id", sa.String(120), nullable=False),
        sa.Column("pin_url", sa.String(1024), nullable=True),
        sa.Column("author_name", sa.String(240), nullable=True),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="suggested"),
        sa.Column("safety_status", sa.String(40), nullable=False, server_default="safe"),
        sa.Column("safety_reason", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "comment_id", name="ux_reply_record_account_comment"),
    )
    op.create_index("ix_reply_record_account_id", "reply_record", ["account_id"])
    op.create_index("ix_reply_record_comment_id", "reply_record", ["comment_id"])
    op.create_index("ix_reply_record_status", "reply_record", ["status"])
    op.create_index("ix_reply_record_account_status", "reply_record", ["account_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_reply_record_account_status", table_name="reply_record")
    op.drop_index("ix_reply_record_status", table_name="reply_record")
    op.drop_index("ix_reply_record_comment_id", table_name="reply_record")
    op.drop_index("ix_reply_record_account_id", table_name="reply_record")
    op.drop_table("reply_record")
