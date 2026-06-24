"""
Эндпоинты генерации отчётов по товарам и конкурентам.
"""

import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.services.report_service import generate_competitor_report
from app.services.limits import enforce_monthly_limit

router = APIRouter()


@router.get(
    "/competitors",
    summary="Отчёт по товарам и конкурентам",
    description="Возвращает файл отчёта (xlsx или pdf) по товарам текущего пользователя",
)
async def download_competitor_report(
    fmt: str = Query(default="xlsx", pattern="^(xlsx|pdf)$", description="Формат: xlsx или pdf"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сформировать и отдать отчёт по товарам/конкурентам пользователя."""
    logger.info(f"📊 Генерация отчёта ({fmt}) для user_id={current_user.id}")

    # Месячный лимит отчётов по тарифу.
    await enforce_monthly_limit(db, current_user.id, "competitor_reports")

    content, filename, media_type = await generate_competitor_report(db, current_user.id, fmt)

    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
