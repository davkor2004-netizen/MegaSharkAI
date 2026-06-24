"""Add widget_configs and usage_counters tables.

Эти таблицы появились как ORM-модели (app/models/widget.py, app/models/usage.py),
но соответствующей миграции не было. В production (где схему накатывает только
Alembic, без create_all) таблицы отсутствовали, из-за чего запросы к
/api/v1/widget/config падали с 500 (relation does not exist).

Revision ID: 20260624_add_widget_and_usage_tables
Revises: 20260616_marketplace_additional_credentials
Create Date: 2026-06-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260624_add_widget_and_usage_tables"
down_revision: Union[str, Sequence[str], None] = "20260616_marketplace_additional_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    """Проверить наличие таблицы (идемпотентность для уже инициализированных БД)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Создать таблицы widget_configs и usage_counters, если их ещё нет."""
    if not _has_table("widget_configs"):
        op.create_table(
            "widget_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("public_key", sa.String(length=64), nullable=False),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "title",
                sa.String(length=120),
                nullable=False,
                server_default="Помощник магазина",
            ),
            sa.Column(
                "welcome_message",
                sa.Text(),
                nullable=False,
                server_default="Здравствуйте! Я помогу выбрать товар и отвечу на вопросы.",
            ),
            sa.Column(
                "accent_color",
                sa.String(length=9),
                nullable=False,
                server_default="#6d28d9",
            ),
            sa.Column("allowed_origins", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_widget_configs_id", "widget_configs", ["id"])
        op.create_index("ix_widget_configs_user_id", "widget_configs", ["user_id"], unique=True)
        op.create_index(
            "ix_widget_configs_public_key", "widget_configs", ["public_key"], unique=True
        )

    if not _has_table("usage_counters"):
        op.create_table(
            "usage_counters",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("metric", sa.String(length=64), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id", "metric", "period", name="uq_usage_user_metric_period"
            ),
        )
        op.create_index("ix_usage_counters_id", "usage_counters", ["id"])
        op.create_index("ix_usage_counters_user_id", "usage_counters", ["user_id"])
        op.create_index("ix_usage_counters_metric", "usage_counters", ["metric"])
        op.create_index("ix_usage_counters_period", "usage_counters", ["period"])


def downgrade() -> None:
    """Удалить таблицы widget_configs и usage_counters."""
    if _has_table("usage_counters"):
        op.drop_index("ix_usage_counters_period", table_name="usage_counters")
        op.drop_index("ix_usage_counters_metric", table_name="usage_counters")
        op.drop_index("ix_usage_counters_user_id", table_name="usage_counters")
        op.drop_index("ix_usage_counters_id", table_name="usage_counters")
        op.drop_table("usage_counters")

    if _has_table("widget_configs"):
        op.drop_index("ix_widget_configs_public_key", table_name="widget_configs")
        op.drop_index("ix_widget_configs_user_id", table_name="widget_configs")
        op.drop_index("ix_widget_configs_id", table_name="widget_configs")
        op.drop_table("widget_configs")
