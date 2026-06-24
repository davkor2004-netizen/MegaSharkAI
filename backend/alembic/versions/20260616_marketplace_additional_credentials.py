"""Add encrypted marketplace additional credentials.

Revision ID: 20260616_marketplace_additional_credentials
Revises: 20260616_user_scoped_product_external_id
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_marketplace_additional_credentials"
down_revision: Union[str, Sequence[str], None] = "20260616_user_scoped_product_external_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    """Проверить наличие колонки (идемпотентность при schema из create_all)."""
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def _has_table(table: str) -> bool:
    """Проверить наличие таблицы."""
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    """Добавить зашифрованные marketplace-specific credentials (идемпотентно)."""
    if not _has_table("marketplace_keys"):
        return

    if not _has_column("marketplace_keys", "additional_credentials_encrypted"):
        op.add_column(
            "marketplace_keys",
            sa.Column("additional_credentials_encrypted", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    """Удалить marketplace-specific credentials."""
    op.drop_column("marketplace_keys", "additional_credentials_encrypted")
