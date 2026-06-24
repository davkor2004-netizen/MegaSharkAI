"""
Сервис управления пулом прокси (Proxy Pool).
Обеспечивает ротацию прокси для парсинга.
"""

import random
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from loguru import logger


class ProxyInfo:
    """Информация об одном прокси."""
    
    def __init__(self, ip: str, port: int, login: str, password: str):
        self.ip = ip
        self.port = port
        self.login = login
        self.password = password
        self.usage_count = 0  # Сколько раз использован
        self.last_used: Optional[datetime] = None
        self.is_blocked = False
        self.block_until: Optional[datetime] = None
        self.error_count = 0
    
    @property
    def proxy_url(self) -> str:
        """URL для Playwright/httpx."""
        return f"http://{self.login}:{self.password}@{self.ip}:{self.port}"
    
    @property
    def is_available(self) -> bool:
        """Доступен ли прокси для использования."""
        if self.is_blocked:
            if self.block_until and datetime.utcnow() > self.block_until:
                self.is_blocked = False
                self.block_until = None
                logger.info(f"🔄 Прокси {self.ip} разблокирован")
                return True
            return False
        return True
    
    def mark_used(self):
        """Отметить прокси как использованный."""
        self.usage_count += 1
        self.last_used = datetime.utcnow()
    
    def mark_error(self):
        """Отметить ошибку использования."""
        self.error_count += 1
        # Если много ошибок — временно блокируем
        if self.error_count >= 5:
            self.block_for(minutes=30)
    
    def mark_success(self):
        """Отметить успешное использование."""
        self.error_count = 0
    
    def block_for(self, minutes: int = 30):
        """Временно заблокировать прокси."""
        self.is_blocked = True
        self.block_until = datetime.utcnow() + timedelta(minutes=minutes)
        logger.warning(f"🚫 Прокси {self.ip} заблокирован на {minutes} мин")
    
    def to_dict(self) -> Dict:
        """Словарь для логирования."""
        return {
            "ip": self.ip,
            "port": self.port,
            "usage_count": self.usage_count,
            "error_count": self.error_count,
            "is_blocked": self.is_blocked,
        }


class ProxyPool:
    """Пул прокси с ротацией."""
    
    def __init__(self):
        self.proxies: List[ProxyInfo] = []
        self.current_index = 0
        self._initialized = False
    
    def initialize(self, proxy_strings: List[str]):
        """
        Инициализация пула прокси.
        
        Args:
            proxy_strings: Список строк формата "ip:port:login:password"
        """
        self.proxies = []
        
        for proxy_str in proxy_strings:
            try:
                parts = proxy_str.strip().split(':')
                if len(parts) != 4:
                    logger.warning(f"⚠️ Неверный формат прокси: {proxy_str}")
                    continue
                
                ip, port, login, password = parts
                proxy = ProxyInfo(
                    ip=ip.strip(),
                    port=int(port.strip()),
                    login=login.strip(),
                    password=password.strip()
                )
                self.proxies.append(proxy)
            
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга прокси {proxy_str}: {e}")
        
        self._initialized = len(self.proxies) > 0
        logger.info(f"✅ Инициализировано {len(self.proxies)} прокси")
    
    def get_next_proxy(self) -> Optional[ProxyInfo]:
        """
        Получить следующий доступный прокси (циклическая ротация).
        
        Returns:
            ProxyInfo или None, если все прокси недоступны
        """
        if not self._initialized:
            logger.warning("⚠️ Пул прокси не инициализирован")
            return None
        
        # Пробуем найти доступный прокси (максимум один круг)
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            
            if proxy.is_available:
                proxy.mark_used()
                logger.debug(f"🔹 Выбран прокси: {proxy.ip}")
                return proxy
        
        logger.warning("⚠️ Все прокси недоступны")
        return None
    
    def get_random_proxy(self) -> Optional[ProxyInfo]:
        """
        Получить случайный доступный прокси.
        
        Returns:
            ProxyInfo или None, если все прокси недоступны
        """
        if not self._initialized:
            return None
        
        available = [p for p in self.proxies if p.is_available]
        
        if not available:
            logger.warning("⚠️ Все прокси недоступны")
            return None
        
        proxy = random.choice(available)
        proxy.mark_used()
        logger.debug(f"🔹 Выбран случайный прокси: {proxy.ip}")
        return proxy
    
    def get_least_used_proxy(self) -> Optional[ProxyInfo]:
        """
        Получить прокси с наименьшей загрузкой.
        
        Returns:
            ProxyInfo или None
        """
        if not self._initialized:
            return None
        
        available = [p for p in self.proxies if p.is_available]
        
        if not available:
            return None
        
        # Сортируем по использованию (наименее использованный первый)
        available.sort(key=lambda p: p.usage_count)
        proxy = available[0]
        proxy.mark_used()
        return proxy
    
    def get_stats(self) -> Dict:
        """Статистика использования пула."""
        if not self.proxies:
            return {"total": 0}
        
        return {
            "total": len(self.proxies),
            "available": sum(1 for p in self.proxies if p.is_available),
            "blocked": sum(1 for p in self.proxies if p.is_blocked),
            "total_usage": sum(p.usage_count for p in self.proxies),
            "avg_usage": sum(p.usage_count for p in self.proxies) / len(self.proxies),
            "proxies": [p.to_dict() for p in self.proxies],
        }
    
    def reset_usage(self):
        """Сбросить счётчики использования (для нового дня)."""
        for proxy in self.proxies:
            proxy.usage_count = 0
        logger.info("🔄 Счётчики использования прокси сброшены")


# Глобальный экземпляр пула
proxy_pool = ProxyPool()


def init_proxy_pool(proxy_strings: List[str]):
    """Инициализировать глобальный пул прокси."""
    proxy_pool.initialize(proxy_strings)


def get_proxy(strategy: str = "least_used") -> Optional[ProxyInfo]:
    """
    Получить прокси из пула.
    
    Args:
        strategy: "next", "random", или "least_used"
    
    Returns:
        ProxyInfo или None
    """
    if strategy == "next":
        return proxy_pool.get_next_proxy()
    elif strategy == "random":
        return proxy_pool.get_random_proxy()
    else:  # least_used
        return proxy_pool.get_least_used_proxy()


def get_proxy_stats() -> Dict:
    """Получить статистику пула."""
    return proxy_pool.get_stats()
