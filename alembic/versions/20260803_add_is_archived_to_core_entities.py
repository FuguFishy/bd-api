"""add is_archived to organisations contacts projects

Revision ID: 20260803_add_is_archived
Revises: <PUT_YOUR_PREVIOUS_REVISION_ID_HERE>
Create Date: 2026-08-03 07:45:00
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260803_add_is_archived"
down_revision = "<PUT_YOUR_PREVIOUS_REVISION_ID_HERE>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organisations",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "contacts",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "projects",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("projects", "is_archived")
    op.drop_column("contacts", "is_archived")
    op.drop_column("organisations", "is_archived")