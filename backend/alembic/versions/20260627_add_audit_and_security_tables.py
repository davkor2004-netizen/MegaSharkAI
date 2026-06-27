"""Add audit_logs and security_events tables.

Централизованный журнал действий (audit_logs) и журнал событий безопасности
(security_events) для Admin Control Center. Раньше /admin/audit и /admin/security
возвращали ``available: false`` из-за отсутствия хранилища — эта миграция его создаёт.

Миграция идемпотентна (guarded): на уже инициализированных БД шаги пропускаются.

Revision ID: 20260627_audit_security
Revises: base_schema_bootstrap
Create Date: 2026-06-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260627_audit_security"
down_revision: Union[str, Sequence[str], None] = "base_schema_bootstrap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    """Проверить наличие таблицы (идемпотентность для уже инициализированных БД)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Создать таблицы audit_logs и security_events, если их ещё нет."""
    if not _has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("target_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("entity_type", sa.String(length=100), nullable=True),
            sa.Column("entity_id", sa.String(length=255), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["actor_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["target_user_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
        op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
        op.create_index("ix_audit_logs_target_user_id", "audit_logs", ["target_user_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    if not _has_table("security_events"):
        op.create_table(
            "security_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False, server_default="info"),
            sa.Column("ip", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=512), nullable=True),
            sa.Column("path", sa.String(length=512), nullable=True),
            sa.Column("method", sa.String(length=16), nullable=True),
            sa.Column("status_code", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_security_events_id", "security_events", ["id"])
        op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
        op.create_index("ix_security_events_event_type", "security_events", ["event_type"])
        op.create_index("ix_security_events_severity", "security_events", ["severity"])
        op.create_index("ix_security_events_created_at", "security_events", ["created_at"])


def downgrade() -> None:
    """Удалить таблицы security_events и audit_logs."""
    if _has_table("security_events"):
        op.drop_index("ix_security_events_created_at", table_name="security_events")
        op.drop_index("ix_security_events_severity", table_name="security_events")
        op.drop_index("ix_security_events_event_type", table_name="security_events")
        op.drop_index("ix_security_events_user_id", table_name="security_events")
        op.drop_index("ix_security_events_id", table_name="security_events")
        op.drop_table("security_events")

    if _has_table("audit_logs"):
        op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
        op.drop_index("ix_audit_logs_action", table_name="audit_logs")
        op.drop_index("ix_audit_logs_target_user_id", table_name="audit_logs")
        op.drop_index("ix_audit_logs_actor_user_id", table_name="audit_logs")
        op.drop_index("ix_audit_logs_id", table_name="audit_logs")
        op.drop_table("audit_logs")
