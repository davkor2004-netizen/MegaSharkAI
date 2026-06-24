"""Initial migration - all tables

Revision ID: 32bc7c876e79
Revises: 
Create Date: 2026-04-15 23:09:59.999551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '32bc7c876e79'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создать все базовые таблицы из metadata моделей (идемпотентный baseline).

    Изначально эта миграция была пустой, и базовые таблицы (users, products,
    notifications и т.д.) создавались только через Base.metadata.create_all на
    старте приложения. Из-за этого чистая Alembic-БД не поднималась: последующие
    миграции добавляют колонки/FK к таблицам, которых ещё нет.

    Теперь initial-миграция (как и заявлено в её названии «all tables») создаёт
    все таблицы из актуального metadata идемпотентно (checkfirst=True):
    - на уже существующей БД (dev/create_all) она давно «применена» и повторно
      не выполняется — нулевой эффект для существующих и production-инсталляций;
    - на чистой БД создаёт полный базовый набор таблиц/индексов, после чего
      инкрементальные миграции (идемпотентные) корректно доезжают до head.
    """
    bind = op.get_bind()

    # pgvector нужен для Product.vector_embedding (VECTOR(768)).
    # На managed-Postgres расширение должно быть предварительно доступно.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Импортируем все ORM-модели, чтобы наполнить общий MetaData.
    import app.models  # noqa: F401 - регистрирует все таблицы в Base.metadata
    from app.core.database import Base

    # checkfirst=True создаёт только отсутствующие таблицы (и их индексы);
    # существующие не трогаются → безопасно для dev и create_all БД.
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    """Initial baseline не дропает таблицы — защита данных (no-op)."""
    pass
