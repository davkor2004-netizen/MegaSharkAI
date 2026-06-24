"""Scope product external IDs by user.

Revision ID: 20260616_user_scoped_product_external_id
Revises: 1234567890ab
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_user_scoped_product_external_id"
down_revision: Union[str, Sequence[str], None] = "1234567890ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(table: str, index: str) -> bool:
    """Проверить наличие индекса (идемпотентность при schema из create_all)."""
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return any(ix["name"] == index for ix in inspector.get_indexes(table))


def _has_table(table: str) -> bool:
    """Проверить наличие таблицы."""
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    """Разрешить разным пользователям хранить один и тот же товар маркетплейса (идемпотентно).

    Если таблицы products ещё нет (чистая Alembic-БД до baseline), пропускаем —
    индекс будет создан в составе таблицы из baseline.
    """
    if not _has_table("products"):
        return

    op.execute("DROP INDEX IF EXISTS ix_products_marketplace_external_id")
    # Новый user-scoped индекс мог быть уже создан через create_all.
    if not _has_index("products", "ix_products_user_marketplace_external_id"):
        op.create_index(
            "ix_products_user_marketplace_external_id",
            "products",
            ["user_id", "marketplace", "external_id"],
            unique=True,
        )


def downgrade() -> None:
    """Вернуть прежний глобальный индекс, если это возможно для данных."""
    op.drop_index("ix_products_user_marketplace_external_id", table_name="products")
    op.create_index(
        "ix_products_marketplace_external_id",
        "products",
        ["marketplace", "external_id"],
        unique=True,
    )
