"""Bootstrap base schema for clean (Alembic-only) databases.

Закрывает структурный долг: ранние initial-миграции (32bc7c876e79,
4e24165aae59) пустые, поэтому базовые таблицы (users, products,
notifications, sale_calendar, user_settings, tariffs, user_subscriptions,
chat_conversations, chat_messages, price_history, competitor_analyses)
исторически создавались только через Base.metadata.create_all и НЕ
создавались ни одной миграцией. На чистой production-БД это приводило
к падению Alembic-цепочки.

Стратегия: append-only baseline ПОСЛЕ текущего head. Создаёт все таблицы
из актуального metadata моделей идемпотентно (checkfirst=True):
- на существующей dev/create_all БД — полный no-op (всё уже есть);
- на чистой БД — создаёт все недостающие базовые таблицы/индексы.

Предыдущие add-column/index миграции уже сделаны идемпотентными и
пропускают шаги, если таблицы ещё нет, поэтому на чистой БД они не падают,
а недостающая схема целиком доезжает этой baseline-миграцией.

Revision ID: base_schema_bootstrap
Revises: 20260624_add_widget_and_usage_tables
Create Date: 2026-06-24
"""

from typing import Sequence, Union

from alembic import op


revision: str = "base_schema_bootstrap"
down_revision: Union[str, Sequence[str], None] = "20260624_add_widget_and_usage_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op.

    Изначально bootstrap-логика планировалась здесь (после head), но из-за
    порядковой зависимости (миграция marketplace_keys создаёт FK на users ещё
    до этого шага) baseline перенесён в initial-миграцию 32bc7c876e79, которая
    выполняется первой. Эта ревизия сохранена как уже применённый на dev no-op
    (удаление файла потребовало бы downgrade + согласования).
    """
    pass


def downgrade() -> None:
    """No-op."""
    pass
