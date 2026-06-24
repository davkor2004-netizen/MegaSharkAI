"""Add marketplace seller fields to User

Revision ID: add_marketplace_seller_fields
Revises: previous_revision
Create Date: 2024-01-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_marketplace_seller_fields'
down_revision = None  # Укажите предыдущую миграцию если есть
branch_labels = None
depends_on = None


def _has_table(table: str) -> bool:
    """Проверить наличие таблицы."""
    return table in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    """Проверить наличие колонки (идемпотентность при schema из create_all)."""
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    """Добавление полей для продавца маркетплейса (идемпотентно).

    Если таблицы users ещё нет (чистая Alembic-БД до baseline-миграции),
    пропускаем — недостающие столбцы будут в составе таблицы из baseline.
    """
    if not _has_table("users"):
        return

    # Добавляем поле is_marketplace_seller, если его ещё нет.
    if not _has_column("users", "is_marketplace_seller"):
        op.add_column(
            'users',
            sa.Column('is_marketplace_seller', sa.Boolean(), nullable=True, server_default='false')
        )
        op.execute("UPDATE users SET is_marketplace_seller = false WHERE is_marketplace_seller IS NULL")
        op.alter_column('users', 'is_marketplace_seller', existing_type=sa.Boolean(), nullable=False, server_default='false')

    # Добавляем поле marketplace_api_key, если его ещё нет.
    if not _has_column("users", "marketplace_api_key"):
        op.add_column(
            'users',
            sa.Column('marketplace_api_key', sa.String(length=500), nullable=True)
        )


def downgrade() -> None:
    """Откат миграции."""
    op.drop_column('users', 'marketplace_api_key')
    op.drop_column('users', 'is_marketplace_seller')
