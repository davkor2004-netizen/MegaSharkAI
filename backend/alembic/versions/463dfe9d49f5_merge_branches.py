"""Merge branches

Revision ID: 463dfe9d49f5
Revises: add_marketplace_seller_fields, add_user_profile_fields
Create Date: 2026-04-21 12:27:05.696631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '463dfe9d49f5'
down_revision: Union[str, Sequence[str], None] = ('add_marketplace_seller_fields', 'add_user_profile_fields')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
