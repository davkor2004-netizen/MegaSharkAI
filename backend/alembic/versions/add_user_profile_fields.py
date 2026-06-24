"""Add user profile fields (phone, two_factor_enabled)

Revision ID: add_user_profile_fields
Revises: 7a5501e460ca
Create Date: 2026-04-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_profile_fields'
down_revision: Union[str, Sequence[str], None] = '7a5501e460ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    """Добавление полей профиля пользователя (идемпотентно).

    Если таблицы users ещё нет (чистая Alembic-БД до baseline-миграции),
    пропускаем — столбцы будут в составе таблицы из baseline.
    """
    if not _has_table("users"):
        return

    # Добавляем поле phone, если его ещё нет (могло быть создано через create_all).
    if not _has_column("users", "phone"):
        op.add_column(
            'users',
            sa.Column('phone', sa.String(length=32), nullable=True)
        )

    # Добавляем поле two_factor_enabled, если его ещё нет.
    if not _has_column("users", "two_factor_enabled"):
        op.add_column(
            'users',
            sa.Column('two_factor_enabled', sa.Boolean(), nullable=True, server_default='false')
        )
        op.execute("UPDATE users SET two_factor_enabled = false WHERE two_factor_enabled IS NULL")
        op.alter_column('users', 'two_factor_enabled', existing_type=sa.Boolean(), nullable=False, server_default='false')


def downgrade() -> None:
    """Откат миграции."""
    op.drop_column('users', 'two_factor_enabled')
    op.drop_column('users', 'phone')
