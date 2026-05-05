"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-26
"""

import os

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
)


def upgrade() -> None:
    sql_path = os.path.join(_project_root, "scripts", "init_db.sql")
    op.execute(open(sql_path, encoding="utf-8").read())


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS token_usage")
    op.execute("DROP TABLE IF EXISTS publish_job")
    op.execute("DROP TABLE IF EXISTS campaign")
    op.execute("DROP TABLE IF EXISTS social_account")
    op.execute("DROP TABLE IF EXISTS global_strategy")
    op.execute("DROP TABLE IF EXISTS pin_performance")
