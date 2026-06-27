"""
Модели журналирования: audit log и события безопасности.

Эти таблицы наполняются append-only (только добавление записей) сервисом
``app.services.audit_service``. В них НИКОГДА не должны попадать сырые секреты:
пароли, токены, API-ключи, cookie — за это отвечает санитизация метаданных.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.core.datetime_utils import utcnow


class AuditLog(Base):
    """
    Журнал административных и значимых действий в системе.

    Хранит "кто что сделал" для последующего аудита. Метаданные (``metadata_json``)
    сохраняются в санитизированном виде — без секретов.
    """

    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="Уникальный идентификатор записи аудита",
    )

    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Кто совершил действие (может быть NULL для системных событий)",
    )

    target_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Над кем совершено действие (если применимо)",
    )

    action = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Код действия, например auth.login, auth.logout",
    )

    entity_type = Column(
        String(100),
        nullable=True,
        comment="Тип сущности, к которой относится действие (user, subscription и т.д.)",
    )

    entity_id = Column(
        String(255),
        nullable=True,
        comment="Идентификатор затронутой сущности (строкой, чтобы поддержать int/uuid)",
    )

    metadata_json = Column(
        Text,
        nullable=True,
        comment="Санитизированные метаданные в формате JSON (без секретов)",
    )

    ip = Column(
        String(64),
        nullable=True,
        comment="IP-адрес инициатора действия",
    )

    user_agent = Column(
        String(512),
        nullable=True,
        comment="User-Agent инициатора действия",
    )

    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False,
        index=True,
        comment="Время события (UTC)",
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action!r})>"


class SecurityEvent(Base):
    """
    Событие безопасности (вход/выход, неудачные попытки, отказы доступа).

    Используется для мониторинга подозрительной активности. ``metadata_json``
    сохраняется санитизированным.
    """

    __tablename__ = "security_events"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        comment="Уникальный идентификатор события безопасности",
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Связанный пользователь (NULL, если неизвестен — например неудачный логин)",
    )

    event_type = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Тип события: login_success, login_failed, logout, token_refresh и т.д.",
    )

    severity = Column(
        String(20),
        nullable=False,
        default="info",
        index=True,
        comment="Уровень: info / warning / high / critical",
    )

    ip = Column(
        String(64),
        nullable=True,
        comment="IP-адрес источника",
    )

    user_agent = Column(
        String(512),
        nullable=True,
        comment="User-Agent источника",
    )

    path = Column(
        String(512),
        nullable=True,
        comment="Путь запроса, если применимо",
    )

    method = Column(
        String(16),
        nullable=True,
        comment="HTTP-метод запроса, если применимо",
    )

    status_code = Column(
        Integer,
        nullable=True,
        comment="HTTP-код ответа, если применимо",
    )

    metadata_json = Column(
        Text,
        nullable=True,
        comment="Санитизированные метаданные в формате JSON (без секретов)",
    )

    created_at = Column(
        DateTime,
        default=utcnow,
        nullable=False,
        index=True,
        comment="Время события (UTC)",
    )

    def __repr__(self) -> str:
        return f"<SecurityEvent(id={self.id}, type={self.event_type!r}, severity={self.severity!r})>"
