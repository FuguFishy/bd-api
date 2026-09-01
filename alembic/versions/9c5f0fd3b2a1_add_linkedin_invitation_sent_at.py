"""add_linkedin_invitation_sent_at

Revision ID: 9c5f0fd3b2a1
Revises: ef87ecc8fd2f
Create Date: 2026-08-21 15:31:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c5f0fd3b2a1"
down_revision: Union[str, Sequence[str], None] = "ef87ecc8fd2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    contact_columns = {
        column["name"]
        for column in inspector.get_columns("contacts")
    }

    if "linkedin_invitation_sent_at" not in contact_columns:
        op.add_column(
            "contacts",
            sa.Column(
                "linkedin_invitation_sent_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    inspector = sa.inspect(bind)
    index_names = {
        index["name"]
        for index in inspector.get_indexes("contacts")
    }

    if "idx_contacts_linkedin_invitation_sent_at" not in index_names:
        op.create_index(
            "idx_contacts_linkedin_invitation_sent_at",
            "contacts",
            ["linkedin_invitation_sent_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    index_names = {
        index["name"]
        for index in inspector.get_indexes("contacts")
    }

    if "idx_contacts_linkedin_invitation_sent_at" in index_names:
        op.drop_index(
            "idx_contacts_linkedin_invitation_sent_at",
            table_name="contacts",
        )

    inspector = sa.inspect(bind)
    contact_columns = {
        column["name"]
        for column in inspector.get_columns("contacts")
    }

    if "linkedin_invitation_sent_at" in contact_columns:
        op.drop_column("contacts", "linkedin_invitation_sent_at")
