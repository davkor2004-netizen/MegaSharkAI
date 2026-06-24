"""
Сервис для шифрования и дешифрования API ключей.
Используем симметричное шифрование AES-256.
"""

from cryptography.fernet import Fernet
import base64
from loguru import logger

from app.config import settings


class EncryptionService:
    """
    Сервис для шифрования конфиденциальных данных.
    """
    
    def __init__(self):
        """
        Инициализация сервиса.
        Ключ шифрования берётся из переменных окружения.
        """
        configured_key = settings.ENCRYPTION_KEY or settings.encryption_key
        if configured_key:
            self.master_key = configured_key.encode()
        elif settings.is_production:
            raise RuntimeError("ENCRYPTION_KEY обязателен для production")
        else:
            # Только для локальной разработки: данные, зашифрованные таким ключом,
            # не переживут рестарт приложения.
            logger.warning("⚠️ ENCRYPTION_KEY не задан. Используется временный dev-ключ.")
            self.master_key = self._generate_key()
        
        # Создаём Fernet объект для шифрования
        self.cipher = Fernet(self.master_key)
    
    def _generate_key(self) -> bytes:
        """
        Генерация нового ключа шифрования.
        Используется только если ключ не задан в настройках.
        """
        # Генерируем случайный ключ
        key = Fernet.generate_key()
        return key
    
    def encrypt(self, data: str) -> str:
        """
        Шифрование строки.
        
        Args:
            data: Строка для шифрования
            
        Returns:
            Зашифрованная строка (base64)
        """
        if not data:
            return ""
        
        # Кодируем строку в байты и шифруем
        encrypted = self.cipher.encrypt(data.encode('utf-8'))
        
        # Возвращаем как base64 строку
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Дешифрование строки.
        
        Args:
            encrypted_data: Зашифрованная строка (base64)
            
        Returns:
            Расшифрованная строка
        """
        if not encrypted_data:
            return ""
        
        try:
            # Декодируем из base64
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            
            # Дешифруем
            decrypted = self.cipher.decrypt(encrypted_bytes)
            
            return decrypted.decode('utf-8')
        except Exception:
            # Не логируем зашифрованное значение или исходные данные.
            logger.warning("⚠️ Не удалось расшифровать защищённое значение")
            return ""


# Глобальный экземпляр сервиса
encryption_service = EncryptionService()
