"""add tagged_topics column to publish_job

Revision ID: 0005_publish_job_tagged_topics
Revises: 0004_reply_record
Create Date: 2026-05-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_publish_job_tagged_topics"
down_revision = "0004_reply_record"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "publish_job",
        sa.Column("tagged_topics", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("publish_job", "tagged_topics")
