"""
Модель учёта потребления тарифных лимитов.

Хранит помесячные счётчики действий пользователя (AI-генерации, отчёты и т.д.),
чтобы enforcement лимитов тарифа был точным и переживал перезапуски.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel


class UsageCounter(BaseModel):
    """
    Счётчик использования по метрике за период.

    Поля:
        user_id: владелец счётчика
        metric: тип действия (ai_generations_per_month, competitor_reports, ...)
        period: период учёта в формате YYYY-MM (для помесячных лимитов)
        count: текущее значение счётчика
    """

    __tablename__ = "usage_counters"

    id = Column(Integer, primary_key=True, index=True, comment="ID счётчика")

    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="ID пользователя",
    )

    metric = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Метрика лимита",
    )

    period = Column(
        String(7),
        nullable=False,
        index=True,
        comment="Период учёта YYYY-MM",
    )

    count = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Текущее значение счётчика",
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Время обновления",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "metric", "period", name="uq_usage_user_metric_period"),
    )

    def __repr__(self) -> str:
        return f"<UsageCounter(user_id={self.user_id}, metric='{self.metric}', count={self.count})>"
