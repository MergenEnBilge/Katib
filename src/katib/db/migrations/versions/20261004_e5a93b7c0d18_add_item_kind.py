"""add item kind

Revision ID: e5a93b7c0d18
Revises: d3f81a5b6c47
"""

from alembic import op
import sqlalchemy as sa


revision = "e5a93b7c0d18"
down_revision = "d3f81a5b6c47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "images",
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="image"),
    )


def downgrade() -> None:
    op.drop_column("images", "kind")
