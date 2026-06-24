"""
Сервис аутентификации для MegaSharkAI.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.config import settings
from app.models.user import User
from app.schemas.user import TokenData
from app.core.database import get_db
from app.core.auth_cookies import ACCESS_TOKEN_COOKIE_NAME


# Настройки безопасности
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"
TOKEN_TYPE_REFRESH = "refresh"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверка пароля.
    
    Args:
        plain_password: Пароль в открытом виде
        hashed_password: Хеш пароля
        
    Returns:
        bool: True если пароль верный
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Хеширование пароля.
    
    Args:
        password: Пароль в открытом виде
        
    Returns:
        str: Хеш пароля
    """
    return pwd_context.hash(password)


def _encode_token(payload: dict) -> str:
    """Подписать JWT payload."""
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def is_access_token_payload(payload: dict) -> bool:
    """
    Проверить, что JWT предназначен для доступа к API.

    Старые токены без поля type считаем access (обратная совместимость).
    Токены password_reset/refresh для REST API отклоняются.
    """
    token_type = payload.get("type")
    if token_type is None:
        return True
    return token_type == TOKEN_TYPE_ACCESS


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание access токена.
    
    Args:
        data: Данные для токена
        expires_delta: Время жизни токена
        
    Returns:
        str: JWT токен
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": TOKEN_TYPE_ACCESS})
    return _encode_token(to_encode)


def create_password_reset_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Создать одноразовый JWT только для сброса пароля (не для API)."""
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=1))
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": TOKEN_TYPE_PASSWORD_RESET,
    }
    return _encode_token(payload)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Создание refresh токена.

    Refresh-токен живёт дольше access-токена и используется только для
    выпуска нового короткоживущего access-токена через /auth/refresh.
    Срок жизни задаётся вызывающей стороной (обычная сессия vs "Запомнить меня").

    Args:
        data: Данные для токена
        expires_delta: Срок жизни токена (по умолчанию REFRESH_TOKEN_EXPIRE_DAYS)

    Returns:
        str: JWT токен
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": TOKEN_TYPE_REFRESH})
    return _encode_token(to_encode)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    """
    Аутентификация пользователя.
    
    Args:
        db: Сессия базы данных
        email: Email пользователя
        password: Пароль
        
    Returns:
        Optional[User]: Пользователь если аутентификация успешна
    """
    result = await db.execute(select(User).filter(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Получение текущего пользователя из Bearer-токена или HttpOnly cookie.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )

    access_token = token or request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not access_token:
        raise credentials_exception
    
    try:
        payload = jwt.decode(access_token, settings.SECRET_KEY, algorithms=[ALGORITHM])

        # Единый формат JWT для проекта: sub хранит UUID пользователя.
        # user_id оставлен как совместимый alias для старых токенов/клиентов.
        token_user_id: str | None = payload.get("sub") or payload.get("user_id")

        if token_user_id is None:
            raise credentials_exception

        if not is_access_token_payload(payload):
            raise credentials_exception
        
        token_data = TokenData(user_id=UUID(token_user_id))
        
    except (JWTError, ValueError):
        raise credentials_exception
    
    result = await db.execute(select(User).filter(User.id == token_data.user_id))
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Получение активного пользователя.
    
    Args:
        current_user: Текущий пользователь
        
    Returns:
        User: Активный пользователь
        
    Raises:
        HTTPException: Если пользователь не активен
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Пользователь не активен")
    
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Получение пользователя с правами администратора.
    
    Args:
        current_user: Текущий пользователь
        
    Returns:
        User: Пользователь с правами администратора
        
    Raises:
        HTTPException: Если пользователь не администратор
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения этого действия"
        )
    
    return current_user


async def get_current_user_from_ws(
    token: str,
    db: AsyncSession,
) -> Optional[User]:
    """
    Получение текущего пользователя из токена для WebSocket.
    
    Args:
        token: JWT токен из query params или сообщения
        db: Сессия базы данных
        
    Returns:
        User: Текущий пользователь или None если токен невалиден
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub") or payload.get("user_id")
        
        if user_id is None:
            return None

        if not is_access_token_payload(payload):
            return None
        
        token_user_id = UUID(user_id)
        
    except (JWTError, ValueError):
        return None
    
    result = await db.execute(select(User).filter(User.id == token_user_id))
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        return None
    
    return user
