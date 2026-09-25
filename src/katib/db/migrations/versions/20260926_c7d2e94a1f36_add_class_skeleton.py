"""add class skeleton

Revision ID: c7d2e94a1f36
Revises: a41c7d9e0b52
"""

from alembic import op
import sqlalchemy as sa


revision = "c7d2e94a1f36"
down_revision = "a41c7d9e0b52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("classes", sa.Column("skeleton", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("classes", "skeleton")
