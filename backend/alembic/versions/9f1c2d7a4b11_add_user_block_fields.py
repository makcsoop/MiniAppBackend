"""add_user_block_fields

Revision ID: 9f1c2d7a4b11
Revises: 3be8df73c7ba
Create Date: 2026-05-05 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f1c2d7a4b11"
down_revision: Union[str, None] = "3be8df73c7ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("users", sa.Column("blocked_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("blocked_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_is_blocked", "users", ["is_blocked"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_is_blocked", table_name="users")
    op.drop_column("users", "blocked_at")
    op.drop_column("users", "blocked_reason")
    op.drop_column("users", "is_blocked")
