"""add project folders

Revision ID: a41c7d9e0b52
Revises: 6eb316d211a3
"""

from alembic import op
import sqlalchemy as sa


revision = "a41c7d9e0b52"
down_revision = "6eb316d211a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_folders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_folders_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_folders")),
        sa.UniqueConstraint("project_id", "path", name=op.f("uq_project_folders_project_id")),
    )


def downgrade() -> None:
    op.drop_table("project_folders")
