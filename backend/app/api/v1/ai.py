"""
Эндпоинты для AI-функционала.
"""

import base64
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.ai_service import get_ai_service, AIService
from app.models.ai_settings import AISettings
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user, get_current_superuser
from app.services.encryption import encryption_service
from app.services.limits import (
    enforce_monthly_limit,
    check_monthly_limit,
    increment_monthly_usage,
)

# Каталог для сохранения сгенерированных изображений (совпадает с mount в main.py).
MEDIA_ROOT = Path(__file__).resolve().parents[3] / "media"
AI_IMAGES_DIR = MEDIA_ROOT / "ai_images"


def get_ai():
    """Зависимость для получения AI-сервиса."""
    return get_ai_service()

router = APIRouter()


class AISettingsRequest(BaseModel):
    """Запрос на сохранение AI-настроек."""
    yandex_api_key: Optional[str] = None
    yandex_folder_id: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


def mask_secret(value: Optional[str]) -> Optional[str]:
    """Возвращает безопасную маску секрета без раскрытия значения."""
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 6)}{value[-4:]}"


def decrypt_setting(value: Optional[str]) -> Optional[str]:
    """
    Расшифровать сохранённое значение.

    Для совместимости с ранними dev-данными допускаем legacy plaintext:
    если расшифровка не удалась, используем исходное значение только внутри backend.
    Наружу оно всё равно никогда не возвращается.
    """
    if not value:
        return None
    decrypted = encryption_service.decrypt(value)
    return decrypted or value


def apply_settings_to_ai_service(settings_row: AISettings) -> AIService:
    """Применить сохранённые ключи к глобальному AI-сервису."""
    ai_svc = get_ai_service()
    ai_svc.yandex_api_key = decrypt_setting(settings_row.yandex_api_key)
    ai_svc.yandex_folder_id = settings_row.yandex_folder_id
    ai_svc.deepseek_api_key = decrypt_setting(settings_row.deepseek_api_key)
    ai_svc.openai_api_key = decrypt_setting(settings_row.openai_api_key)
    ai_svc.provider = ai_svc._detect_provider()
    return ai_svc


class SeoTitleRequest(BaseModel):
    """Запрос на генерацию SEO-названия."""
    product_name: str = Field(..., min_length=2, max_length=300)
    category: Optional[str] = Field(None, max_length=150)
    brand: Optional[str] = Field(None, max_length=150)
    characteristics: Optional[Dict[str, Any]] = None


class SeoTitleResponse(BaseModel):
    """Ответ с SEO-названием."""
    original_name: str
    seo_name: str
    provider: str


class CompetitorItem(BaseModel):
    """Данные одного конкурента для AI-анализа."""
    name: str = Field(..., min_length=1, max_length=300)
    price: float = Field(..., gt=0, le=10_000_000)
    rating: Optional[float] = Field(None, ge=0, le=5)


class CompetitorAnalysisRequest(BaseModel):
    """Запрос на анализ конкурентов."""
    product_name: str = Field(..., min_length=2, max_length=300)
    competitors: List[CompetitorItem] = Field(..., min_length=1, max_length=50)


class CompetitorAnalysisResponse(BaseModel):
    """Ответ с анализом конкурентов."""
    product_name: str
    analysis: Dict[str, Any]
    competitors_count: int


@router.post(
    "/generate-seo-title",
    response_model=SeoTitleResponse,
    summary="Генерация SEO-названия товара",
    description="Создаёт оптимизированное название для маркетплейсов",
)
async def generate_seo_title(
    request: SeoTitleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_svc=Depends(get_ai),
):
    """
    Генерация SEO-оптимизированного названия товара.
    
    Использует AI (Яндекс GPT / DeepSeek / OpenAI) для создания
    продающего названия с ключевыми словами.
    
    **Пример запроса:**
    ```json
    {
        "product_name": "Футболка мужская",
        "category": "Одежда",
        "brand": "Nike",
        "characteristics": {
            "Материал": "Хлопок",
            "Цвет": "Белый",
            "Размер": "L"
        }
    }
    ```
    """
    logger.info(f"🤖 Генерация SEO-названия: user_id={current_user.id}")

    # Проверяем месячный лимит AI-генераций тарифа.
    await enforce_monthly_limit(db, current_user.id, "ai_generations_per_month")

    seo_name = await ai_svc.generate_seo_title(
        product_name=request.product_name,
        category=request.category,
        brand=request.brand,
        characteristics=request.characteristics,
    )
    
    return SeoTitleResponse(
        original_name=request.product_name,
        seo_name=seo_name,
        provider=ai_svc.last_used_provider if ai_svc.last_used_provider != "none" else ai_svc.provider,
    )


@router.post(
    "/analyze-competitors",
    response_model=CompetitorAnalysisResponse,
    summary="AI-анализ конкурентов",
    description="Анализирует цены и позиции конкурентов",
)
async def analyze_competitors(
    request: CompetitorAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_svc=Depends(get_ai),
):
    """
    AI-анализ конкурентов.
    
    Сравнивает товар с конкурентами и даёт рекомендации по ценообразованию.
    
    **Пример запроса:**
    ```json
    {
        "product_name": "Футболка мужская Nike",
        "competitors": [
            {"name": "Футболка Adidas", "price": 2500, "rating": 4.5},
            {"name": "Футболка Puma", "price": 2200, "rating": 4.3},
            {"name": "Футболка Reebok", "price": 1999, "rating": 4.0}
        ]
    }
    ```
    """
    logger.info(f"🤖 Анализ конкурентов: user_id={current_user.id}")

    await enforce_monthly_limit(db, current_user.id, "ai_generations_per_month")

    analysis = await ai_svc.analyze_competitors(
        product_name=request.product_name,
        competitor_data=[competitor.model_dump(exclude_none=True) for competitor in request.competitors],
    )
    
    return CompetitorAnalysisResponse(
        product_name=request.product_name,
        analysis=analysis,
        competitors_count=len(request.competitors),
    )


class ReviewAnswerRequest(BaseModel):
    """Запрос на генерацию ответа на отзыв/вопрос."""
    product_name: str = Field(..., min_length=2, max_length=300)
    review_text: str = Field(..., min_length=2, max_length=2000)
    rating: Optional[float] = Field(None, ge=1, le=5)
    is_question: bool = Field(default=False)


class SeoKeywordsRequest(BaseModel):
    """Запрос на подбор SEO-ключей."""
    product_name: str = Field(..., min_length=2, max_length=300)
    category: Optional[str] = Field(None, max_length=150)


class SkuAuditRequest(BaseModel):
    """Запрос на аудит карточки товара."""
    product_name: str = Field(..., min_length=2, max_length=300)
    description: Optional[str] = Field(None, max_length=5000)
    characteristics: Optional[Dict[str, Any]] = None
    images_count: int = Field(default=0, ge=0, le=100)


@router.post(
    "/answer-review",
    summary="AI-ответ на отзыв или вопрос",
    description="Генерирует вежливый ответ продавца на отзыв/вопрос покупателя",
)
async def answer_review(
    request: ReviewAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_svc=Depends(get_ai),
):
    """Сгенерировать ответ на отзыв или вопрос покупателя."""
    logger.info(f"🤖 Ответ на отзыв: user_id={current_user.id}")
    await enforce_monthly_limit(db, current_user.id, "ai_generations_per_month")

    answer = await ai_svc.answer_review(
        product_name=request.product_name,
        review_text=request.review_text,
        rating=request.rating,
        is_question=request.is_question,
    )
    return {
        "answer": answer,
        "provider": ai_svc.last_used_provider if ai_svc.last_used_provider != "none" else ai_svc.provider,
    }


@router.post(
    "/seo-keywords",
    summary="Подбор SEO-ключей",
    description="Подбирает и кластеризует поисковые запросы для карточки",
)
async def seo_keywords(
    request: SeoKeywordsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_svc=Depends(get_ai),
):
    """Подобрать и кластеризовать ключевые слова для товара."""
    logger.info(f"🤖 Подбор SEO-ключей: user_id={current_user.id}")
    await enforce_monthly_limit(db, current_user.id, "ai_generations_per_month")

    return await ai_svc.generate_seo_keywords(
        product_name=request.product_name,
        category=request.category,
    )


@router.post(
    "/sku-audit",
    summary="SKU-аудит карточки",
    description="Оценивает качество карточки товара и даёт рекомендации",
)
async def sku_audit(
    request: SkuAuditRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_svc=Depends(get_ai),
):
    """Провести аудит карточки товара (оценка + рекомендации)."""
    logger.info(f"🤖 SKU-аудит: user_id={current_user.id}")
    await enforce_monthly_limit(db, current_user.id, "ai_generations_per_month")

    return await ai_svc.audit_sku(
        product_name=request.product_name,
        description=request.description,
        characteristics=request.characteristics,
        images_count=request.images_count,
    )


class ImageGenRequest(BaseModel):
    """Запрос на генерацию изображения."""
    prompt: str = Field(..., min_length=3, max_length=2000, description="Описание изображения")
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = Field(default="1024x1024")
    n: int = Field(default=1, ge=1, le=4, description="Количество вариантов")
    quality: Literal["low", "medium", "high"] = Field(default="high")


@router.post(
    "/generate-image",
    summary="AI-генерация изображения (OpenAI)",
    description="Генерирует предметное фото/инфографику через OpenAI gpt-image-1",
)
async def generate_image(
    request: ImageGenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ai_svc=Depends(get_ai),
):
    """
    Сгенерировать изображение по текстовому описанию.

    Лимит расходуется только при успешной генерации (изображения платные).
    Файлы сохраняются и доступны по URL /media/ai_images/...
    """
    logger.info(f"🎨 Генерация изображения: user_id={current_user.id}")

    # Проверяем лимит без списания (списание — только при успехе).
    await check_monthly_limit(db, current_user.id, "ai_images_per_month", request.n)

    result = await ai_svc.generate_image(
        prompt=request.prompt,
        size=request.size,
        n=request.n,
        quality=request.quality,
    )

    if result.get("status") == "not_configured":
        raise HTTPException(status_code=400, detail=result.get("message"))
    if result.get("status") != "ok":
        raise HTTPException(status_code=502, detail=result.get("message", "Ошибка генерации изображения"))

    # Сохраняем изображения на диск и формируем ссылки.
    AI_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    urls: List[str] = []
    for image_b64 in result["images"]:
        try:
            binary = base64.b64decode(image_b64)
        except Exception:
            continue
        filename = f"{current_user.id}_{uuid.uuid4().hex}.png"
        (AI_IMAGES_DIR / filename).write_bytes(binary)
        urls.append(f"/media/ai_images/{filename}")

    if not urls:
        raise HTTPException(status_code=502, detail="Не удалось сохранить сгенерированные изображения")

    # Списываем лимит по фактически сгенерированным изображениям.
    await increment_monthly_usage(db, current_user.id, "ai_images_per_month", len(urls))

    return {
        "status": "ok",
        "model": result.get("model", "gpt-image-1"),
        "images": urls,
        "count": len(urls),
    }


@router.get(
    "/provider",
    response_model=Dict[str, str],
    summary="Текущий AI-провайдер",
    description="Возвращает информацию о настроенном AI-провайдере",
)
async def get_ai_provider(
    current_user: User = Depends(get_current_user),
    ai_svc=Depends(get_ai),
):
    """
    Проверка текущего AI-провайдера.
    """
    return {
        "provider": ai_svc.provider,
        "status": "configured" if ai_svc.provider != "none" else "not_configured",
    }


@router.post(
    "/test",
    response_model=SeoTitleResponse,
    summary="Тест AI-провайдера",
    description="Тестирует работу AI с помощью стандартного запроса",
)
async def test_ai(
    request: SeoTitleRequest,
    current_user: User = Depends(get_current_superuser),
    ai_svc=Depends(get_ai),
):
    """
    Тестирование AI-провайдера.
    
    Генерирует SEO-название для тестового товара.
    """
    logger.info(f"🧪 Тестирование AI-провайдера: admin_id={current_user.id}")
    
    seo_name = await ai_svc.generate_seo_title(
        product_name=request.product_name,
        category=request.category,
        brand=request.brand,
        characteristics=request.characteristics,
    )
    
    return SeoTitleResponse(
        original_name=request.product_name,
        seo_name=seo_name,
        provider=ai_svc.last_used_provider if ai_svc.last_used_provider != "none" else ai_svc.provider,
    )


@router.post(
    "/settings",
    response_model=Dict[str, str],
    summary="Сохранение AI-настроек",
    description="Сохраняет API-ключи в базу данных",
)
async def save_ai_settings(
    request: AISettingsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Сохранение настроек AI-провайдеров.
    
    Ключи сохраняются в базу данных и применяются к текущему сервису.
    """
    try:
        logger.info(f"💾 Сохранение AI-настроек: admin_id={current_user.id}")
        
        # Получаем или создаём настройки
        result = await db.execute(select(AISettings).limit(1))
        settings = result.scalar_one_or_none()
        
        if not settings:
            settings = AISettings()
            db.add(settings)
            await db.flush()
        
        # Обновляем значения
        if request.yandex_api_key:
            settings.yandex_api_key = encryption_service.encrypt(request.yandex_api_key)
        if request.yandex_folder_id:
            settings.yandex_folder_id = request.yandex_folder_id
        if request.deepseek_api_key:
            settings.deepseek_api_key = encryption_service.encrypt(request.deepseek_api_key)
        if request.openai_api_key:
            settings.openai_api_key = encryption_service.encrypt(request.openai_api_key)
        
        # Обновляем сервис
        ai_svc = apply_settings_to_ai_service(settings)
        
        # Переопределяем провайдер
        ai_svc.provider = ai_svc._detect_provider()
        settings.current_provider = ai_svc.provider
        
        await db.commit()
        await db.refresh(settings)
        
        logger.info(f"✅ AI-настройки сохранены. Текущий провайдер: {ai_svc.provider}")
        
        return {
            "status": "success",
            "provider": ai_svc.provider,
            "message": "Настройки сохранены в базу данных",
        }
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения AI-настроек: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения AI-настроек")


@router.get(
    "/settings",
    response_model=Dict[str, str],
    summary="Получение AI-настроек",
    description="Возвращает сохранённые API-ключи (без значений)",
)
async def get_ai_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
):
    """
    Получение сохранённых настроек.
    """
    try:
        result = await db.execute(select(AISettings).limit(1))
        settings = result.scalar_one_or_none()
        
        if not settings:
            return {
                "provider": "none",
                "yandex_configured": "false",
                "deepseek_configured": "false",
                "openai_configured": "false",
            }
        
        return {
            "provider": settings.current_provider or "none",
            "yandex_configured": "true" if settings.yandex_api_key else "false",
            "yandex_api_key_masked": mask_secret(decrypt_setting(settings.yandex_api_key)) or "",
            "deepseek_configured": "true" if settings.deepseek_api_key else "false",
            "deepseek_api_key_masked": mask_secret(decrypt_setting(settings.deepseek_api_key)) or "",
            "openai_configured": "true" if settings.openai_api_key else "false",
            "openai_api_key_masked": mask_secret(decrypt_setting(settings.openai_api_key)) or "",
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения AI-настроек: {e}")
        # Возвращаем настройки по умолчанию при ошибке БД
        return {
            "provider": "none",
            "yandex_configured": "false",
            "deepseek_configured": "false",
            "openai_configured": "false",
            "error": "settings_unavailable",
        }
    
