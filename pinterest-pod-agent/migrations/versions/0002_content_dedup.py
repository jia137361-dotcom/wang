"""add content dedup hash fields

Revision ID: 0002_content_dedup
Revises: 0001_initial
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_content_dedup"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # publish_job new columns — use IF NOT EXISTS guards because
    # 0001_initial executes init_db.sql which may already create these.
    _add_column_if_not_exists("publish_job", sa.Column("content_hash", sa.String(64), nullable=True))
    _add_column_if_not_exists("publish_job", sa.Column("title_hash", sa.String(64), nullable=True))
    _add_column_if_not_exists("publish_job", sa.Column("description_hash", sa.String(64), nullable=True))
    _add_column_if_not_exists("publish_job", sa.Column("content_batch_id", sa.String(64), nullable=True))
    _add_column_if_not_exists("publish_job", sa.Column("variant_angle", sa.String(160), nullable=True))
    _create_index_if_not_exists("ix_publish_job_content_hash", "publish_job", ["content_hash"])
    _create_index_if_not_exists("ix_publish_job_title_hash", "publish_job", ["title_hash"])
    _create_index_if_not_exists("ix_publish_job_description_hash", "publish_job", ["description_hash"])
    _create_index_if_not_exists("ix_publish_job_content_batch_id", "publish_job", ["content_batch_id"])

    # pin_performance new columns
    _add_column_if_not_exists("pin_performance", sa.Column("content_hash", sa.String(64), nullable=True))
    _add_column_if_not_exists("pin_performance", sa.Column("title_hash", sa.String(64), nullable=True))
    _add_column_if_not_exists("pin_performance", sa.Column("description_hash", sa.String(64), nullable=True))
    _add_column_if_not_exists("pin_performance", sa.Column("content_batch_id", sa.String(64), nullable=True))
    _add_column_if_not_exists("pin_performance", sa.Column("variant_angle", sa.String(160), nullable=True))
    _create_index_if_not_exists("ix_pin_performance_content_hash", "pin_performance", ["content_hash"])
    _create_index_if_not_exists("ix_pin_performance_title_hash", "pin_performance", ["title_hash"])
    _create_index_if_not_exists("ix_pin_performance_description_hash", "pin_performance", ["description_hash"])
    _create_index_if_not_exists("ix_pin_performance_content_batch_id", "pin_performance", ["content_batch_id"])


def _add_column_if_not_exists(table: str, column: sa.Column) -> None:
    """Add a column only if it doesn't already exist (safe after init_db.sql)."""
    from alembic import op

    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing = [c["name"] for c in insp.get_columns(table)]
    if column.name not in existing:
        op.add_column(table, column)


def _create_index_if_not_exists(index_name: str, table: str, columns: list[str]) -> None:
    """Create an index only if it doesn't already exist."""
    from alembic import op

    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_idxs = [i["name"] for i in insp.get_indexes(table)]
    if index_name not in existing_idxs:
        op.create_index(index_name, table, columns)


def downgrade() -> None:
    # pin_performance
    op.drop_index("ix_pin_performance_content_batch_id", table_name="pin_performance")
    op.drop_index("ix_pin_performance_title_hash", table_name="pin_performance")
    op.drop_index("ix_pin_performance_content_hash", table_name="pin_performance")
    op.drop_column("pin_performance", "variant_angle")
    op.drop_column("pin_performance", "content_batch_id")
    op.drop_column("pin_performance", "description_hash")
    op.drop_column("pin_performance", "title_hash")
    op.drop_column("pin_performance", "content_hash")

    # publish_job
    op.drop_index("ix_publish_job_content_batch_id", table_name="publish_job")
    op.drop_index("ix_publish_job_title_hash", table_name="publish_job")
    op.drop_index("ix_publish_job_content_hash", table_name="publish_job")
    op.drop_column("publish_job", "variant_angle")
    op.drop_column("publish_job", "content_batch_id")
    op.drop_column("publish_job", "description_hash")
    op.drop_column("publish_job", "title_hash")
    op.drop_column("publish_job", "content_hash")
