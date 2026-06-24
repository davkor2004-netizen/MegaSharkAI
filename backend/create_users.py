"""
Скрипт для создания начального администратора MegaSharkAI.

Запуск:
    python create_admin.py
"""

import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import settings

# Создаём синхронный движок для скрипта
SYNC_DATABASE_URL = settings.database_url.replace(
    "postgresql+asyncpg://",
    "postgresql://"
)
engine = create_engine(SYNC_DATABASE_URL)

from app.models.user import User
from app.models.tariff import UserSubscription  # Импортируем для корректной работы связей
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Хеширование пароля."""
    return pwd_context.hash(password)


def create_initial_admin(db: Session):
    """
    Создание начального администратора.
    
    Args:
        db: Сессия базы данных
    """
    # Данные админа
    admin_email = "admin@megashark.ai"
    admin_password = "Admin@123456"
    admin_name = "Администратор MegaShark"
    
    # Проверка существования
    existing_admin = db.query(User).filter(User.email == admin_email).first()
    
    if existing_admin:
        print(f"⚠️  Администратор уже существует: {admin_email}")
        print(f"   ID: {existing_admin.id}")
        print(f"   Активен: {existing_admin.is_active}")
        print(f"   Суперпользователь: {existing_admin.is_superuser}")
        
        # Если не суперпользователь, делаем им
        if not existing_admin.is_superuser:
            existing_admin.is_superuser = True
            db.commit()
            print(f"✅ Права администратора выданы")
        return
    
    # Создание администратора
    hashed_password = get_password_hash(admin_password)
    new_admin = User(
        email=admin_email,
        hashed_password=hashed_password,
        full_name=admin_name,
        is_active=True,
        is_superuser=True,  # Права администратора
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    print("✅ Администратор успешно создан!")
    print(f"   Email: {admin_email}")
    print(f"   Пароль: {admin_password}")
    print(f"   ID: {new_admin.id}")
    print(f"\n⚠️  Смените пароль после первого входа!")


def create_test_user(db: Session):
    """
    Создание тестового обычного пользователя.
    
    Args:
        db: Сессия базы данных
    """
    user_email = "user@megashark.ai"
    user_password = "User@123456"
    user_name = "Тестовый пользователь"
    
    # Проверка существования
    existing_user = db.query(User).filter(User.email == user_email).first()
    
    if existing_user:
        print(f"ℹ️  Тестовый пользователь уже существует: {user_email}")
        return
    
    # Создание пользователя
    hashed_password = get_password_hash(user_password)
    new_user = User(
        email=user_email,
        hashed_password=hashed_password,
        full_name=user_name,
        is_active=True,
        is_superuser=False,  # Обычный пользователь
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    print("✅ Тестовый пользователь создан!")
    print(f"   Email: {user_email}")
    print(f"   Пароль: {user_password}")
    print(f"   ID: {new_user.id}")


if __name__ == "__main__":
    print("🦈 MegaSharkAI - Создание пользователей\n")
    
    # Создаем сессию БД
    db = Session(bind=engine)
    
    try:
        # Создаем администратора
        create_initial_admin(db)
        print()
        
        # Создаем тестового пользователя
        create_test_user(db)
        print()
        
        print("✅ Готово!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    finally:
        db.close()
