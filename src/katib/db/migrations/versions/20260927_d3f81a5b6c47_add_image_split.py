"""add image split

Revision ID: d3f81a5b6c47
Revises: c7d2e94a1f36
"""

from alembic import op
import sqlalchemy as sa


revision = "d3f81a5b6c47"
down_revision = "c7d2e94a1f36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("images", sa.Column("split", sa.String(length=10), nullable=True))
    op.create_index("ix_images_project_split", "images", ["project_id", "split"])


def downgrade() -> None:
    op.drop_index("ix_images_project_split", table_name="images")
    op.drop_column("images", "split")
