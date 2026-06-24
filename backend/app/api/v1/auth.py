"""
Эндпоинты для аутентификации и регистрации.

JWT-токены, регистрация, логин, профиль пользователя, сброс пароля.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Request, Response, Form
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
import uuid

from app.core.database import get_db
from app.core.auth_cookies import (
    set_access_token_cookie,
    clear_access_token_cookie,
    set_refresh_token_cookie,
    clear_refresh_token_cookie,
    REFRESH_TOKEN_COOKIE_NAME,
)
from app.schemas.validators import validate_password_strength
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, Token as TokenResponse
from app.config import settings
from app.services.auth_service import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    create_password_reset_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    TOKEN_TYPE_PASSWORD_RESET,
    TOKEN_TYPE_REFRESH,
    get_current_user,
    get_current_superuser,
)
from app.services.rate_limit import enforce_auth_rate_limit


def _refresh_session_max_age_seconds(remember_me: bool) -> int:
    """Срок жизни refresh-сессии в секундах с учётом "Запомнить меня"."""
    days = (
        settings.remember_me_refresh_token_expire_days
        if remember_me
        else settings.refresh_token_expire_days
    )
    return days * 24 * 60 * 60


router = APIRouter()


# ====================
# Эндпоинты
# ====================

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
    description="Создаёт новый аккаунт продавца и возвращает токен",
)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(enforce_auth_rate_limit),
):
    """
    Регистрация нового пользователя.
    
    **Пример запроса:**
    ```json
    {
        "email": "seller@example.com",
        "password": "SecurePass123!",
        "full_name": "Иван Петров"
    }
    ```
    """
    logger.info(f"📝 Регистрация пользователя: {user_data.email}")
    
    # Проверка существования
    result = await db.execute(select(User).filter(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким email уже существует",
        )
    
    # Создание пользователя
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        is_active=True,
        is_superuser=False,
        is_marketplace_seller=user_data.is_marketplace_seller,
        marketplace_api_key=user_data.marketplace_api_key,
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    logger.info(f"✅ Пользователь зарегистрирован: {new_user.id}")
    
    # Создаём и возвращаем токен
    access_token = create_access_token(
        data={"sub": str(new_user.id), "user_id": str(new_user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Refresh-сессия с обычным сроком: новый пользователь не теряет вход
    # после истечения короткого access-токена.
    refresh_max_age = _refresh_session_max_age_seconds(remember_me=False)
    refresh_token = create_refresh_token(
        data={"sub": str(new_user.id), "user_id": str(new_user.id)},
        expires_delta=timedelta(seconds=refresh_max_age),
    )

    response = JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(new_user.id),
                "email": new_user.email,
                "full_name": new_user.full_name,
                "is_marketplace_seller": new_user.is_marketplace_seller,
            },
        },
    )
    set_access_token_cookie(response, access_token)
    set_refresh_token_cookie(response, refresh_token, refresh_max_age)
    return response


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход в систему",
    description="Получение JWT токена для доступа к API",
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    remember_me: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(enforce_auth_rate_limit),
):
    """
    Вход в систему.

    Опциональное поле формы `remember_me` (по умолчанию False) продлевает
    срок жизни refresh-сессии. Старые клиенты без этого поля работают как раньше.
    """
    logger.info(f"🔑 Вход пользователя: {form_data.username} (remember_me={remember_me})")
    
    try:
        # Поиск пользователя
        result = await db.execute(select(User).filter(User.email == form_data.username))
        user = result.scalar_one_or_none()
        
        if not user or not verify_password(form_data.password, user.hashed_password):
            logger.warning(f"❌ Неверные данные входа для: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            logger.warning(f"❌ Аккаунт не активен: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт не активен",
            )
        
        # Короткоживущий access-токен (TTL не зависит от remember_me).
        access_token = create_access_token(
            data={"sub": str(user.id), "user_id": str(user.id)},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        # Refresh-токен задаёт длительность сессии: remember_me продлевает именно его.
        refresh_max_age = _refresh_session_max_age_seconds(remember_me)
        refresh_token = create_refresh_token(
            data={"sub": str(user.id), "user_id": str(user.id)},
            expires_delta=timedelta(seconds=refresh_max_age),
        )

        logger.info(f"✅ Пользователь вошёл: {user.id}")

        response = JSONResponse(
            content={
                "access_token": access_token,
                "token_type": "bearer",
                "is_superuser": user.is_superuser,
            }
        )
        set_access_token_cookie(response, access_token)
        set_refresh_token_cookie(response, refresh_token, refresh_max_age)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка при входе: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера",
        )
    

@router.post(
    "/refresh",
    summary="Обновление сессии",
    description="Выпускает новый короткоживущий access-токен по refresh cookie",
)
async def refresh_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Обновление access-токена по refresh cookie.

    Не продлевает саму refresh-сессию (её срок задан при логине), а лишь
    выпускает новый короткоживущий access-токен. Это позволяет "Запомнить меня"
    работать без длинного access-токена.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Сессия истекла, войдите снова",
        headers={"WWW-Authenticate": "Bearer"},
    )

    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    if not refresh_token:
        raise credentials_exception

    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != TOKEN_TYPE_REFRESH:
            raise credentials_exception

        token_user_id: str | None = payload.get("sub") or payload.get("user_id")
        if token_user_id is None:
            raise credentials_exception

        user_uuid = uuid.UUID(token_user_id)
    except (JWTError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).filter(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    access_token = create_access_token(
        data={"sub": str(user.id), "user_id": str(user.id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    response = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "is_superuser": user.is_superuser,
        }
    )
    set_access_token_cookie(response, access_token)
    return response


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Текущий пользователь",
    description="Возвращает информацию о текущем пользователе",
)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Получение информации о текущем пользователе.
    
    Требует авторизации (Bearer токен).
    """
    return current_user


@router.post(
    "/logout",
    summary="Выход из системы",
    description="Удаляет HttpOnly cookie с JWT",
)
async def logout():
    """Выход: очищает access и refresh cookie независимо от remember_me."""
    response = JSONResponse(content={"status": "success", "message": "Вы вышли из системы"})
    clear_access_token_cookie(response)
    clear_refresh_token_cookie(response)
    return response


@router.get(
    "/me/admin",
    response_model=UserResponse,
    summary="Проверка прав администратора",
    description="Возвращает информацию о текущем пользователе только если это администратор",
)
async def get_admin_me(current_user: User = Depends(get_current_superuser)):
    """
    Проверка прав администратора.
    
    Требует авторизации и роли суперпользователя.
    """
    return current_user


# ====================
# Профиль пользователя
# ====================

class UserProfileUpdate(BaseModel):
    """Схема для обновления профиля пользователя."""
    
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=32)
    marketplace_api_key: Optional[str] = None
    is_marketplace_seller: Optional[bool] = None


class PasswordChange(BaseModel):
    """Схема для смены пароля."""
    
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, value: str) -> str:
        return validate_password_strength(value)


class PasswordResetRequest(BaseModel):
    """Запрос на сброс пароля."""
    
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Подтверждение сброса пароля."""
    
    token: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, value: str) -> str:
        return validate_password_strength(value)


@router.put(
    "/profile",
    response_model=UserResponse,
    summary="Обновить профиль",
    description="Обновление данных профиля текущего пользователя",
)
async def update_profile(
    profile_data: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Обновление профиля пользователя.
    
    Можно изменить:
    - email
    - full_name
    - phone
    - marketplace_api_key
    - is_marketplace_seller
    """
    logger.info(f"✏️ Обновление профиля: user_id={current_user.id}")
    
    # Проверка email на уникальность (если меняется)
    if profile_data.email and profile_data.email != current_user.email:
        result = await db.execute(select(User).filter(User.email == profile_data.email))
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email уже занят другим пользователем",
            )
        current_user.email = profile_data.email
    
    if profile_data.full_name is not None:
        current_user.full_name = profile_data.full_name
    
    if profile_data.phone is not None:
        current_user.phone = profile_data.phone
    
    if profile_data.marketplace_api_key is not None:
        current_user.marketplace_api_key = profile_data.marketplace_api_key
    
    if profile_data.is_marketplace_seller is not None:
        current_user.is_marketplace_seller = profile_data.is_marketplace_seller
    
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(f"✅ Профиль обновлён: user_id={current_user.id}")
    
    return current_user


@router.post(
    "/change-password",
    summary="Сменить пароль",
    description="Изменение пароля текущего пользователя",
)
async def change_password(
    password_data: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Смена пароля.
    
    Требуется текущий пароль для подтверждения.
    """
    logger.info(f"🔑 Смена пароля: user_id={current_user.id}")
    
    # Проверка текущего пароля
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль",
        )
    
    # Установка нового пароля
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    
    logger.info(f"✅ Пароль изменён: user_id={current_user.id}")
    
    return {"status": "success", "message": "Пароль успешно изменён"}


@router.post(
    "/reset-password-request",
    summary="Запросить сброс пароля",
    description="Отправка ссылки для сброса пароля на email",
)
async def reset_password_request(
    reset_data: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(enforce_auth_rate_limit),
):
    """
    Запрос на сброс пароля.
    
    Отправляет email со ссылкой для сброса пароля.
    """
    logger.info(f"📧 Запрос сброса пароля: {reset_data.email}")
    
    result = await db.execute(select(User).filter(User.email == reset_data.email))
    user = result.scalar_one_or_none()
    
    if not user:
        # Не раскрываем, существует ли email (безопасность)
        return {"status": "success", "message": "Если email существует, ссылка отправлена"}
    
    # Токен только для сброса пароля (не принимается API как access)
    reset_token = create_password_reset_token(str(user.id))
    
    # Формирование ссылки
    from app.config import settings
    reset_link = f"{settings.app_url}/reset-password?token={reset_token}"
    
    # Отправка email (если настроен SMTP)
    try:
        from app.services.email import get_email_service
        email_service = get_email_service()
        
        if email_service and email_service.smtp_user:
            email_service.send_password_reset(
                to_email=user.email,
                reset_link=reset_link,
                user_name=user.full_name,
            )
            logger.info(f"✅ Email со ссылкой для сброса отправлен на {user.email}")
        else:
            # Reset token не пишем в логи: это credential уровня пароля.
            logger.warning("⚠️ SMTP не настроен. Ссылка сброса пароля не отправлена.")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки email: {e}")
        
    return {
        "status": "success",
        "message": "Если email существует, ссылка для сброса пароля отправлена",
    }


@router.post(
    "/reset-password-confirm",
    summary="Подтвердить сброс пароля",
    description="Установка нового пароля по токену",
)
async def reset_password_confirm(
    confirm_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """
    Подтверждение сброса пароля.
    """
    logger.info("🔑 Подтверждение сброса пароля")
    
    try:
        payload = jwt.decode(confirm_data.token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if token_type != TOKEN_TYPE_PASSWORD_RESET:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный тип токена",
            )
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный токен",
            )
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или истёкший токен",
        )
    
    result = await db.execute(select(User).filter(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Установка нового пароля
    user.hashed_password = get_password_hash(confirm_data.new_password)
    await db.commit()
    
    logger.info(f"✅ Пароль сброшен: user_id={user.id}")
    
    return {"status": "success", "message": "Пароль успешно изменён"}
