"""add content templates

Revision ID: 0006_content_template
Revises: 0005_publish_job_tagged_topics
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_content_template"
down_revision = "0005_publish_job_tagged_topics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_template",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("template_type", sa.String(length=40), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "template_type", name="ux_content_template_scope_type"),
    )
    op.create_index("ix_content_template_scope", "content_template", ["scope"])
    op.create_index("ix_content_template_template_type", "content_template", ["template_type"])


def downgrade() -> None:
    op.drop_index("ix_content_template_template_type", table_name="content_template")
    op.drop_index("ix_content_template_scope", table_name="content_template")
    op.drop_table("content_template")
