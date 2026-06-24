"""
Проверка URL перед парсингом (защита от SSRF).

Разрешаем только известные домены маркетплейсов и блокируем
localhost, private IP и поддельные host в path/query.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


class UrlSecurityError(Exception):
    """Небезопасный или неподдерживаемый URL для парсинга."""


# Маркетплейс → разрешённые суффиксы hostname (точное совпадение или поддомен)
MARKETPLACE_HOST_SUFFIXES: dict[str, tuple[str, ...]] = {
    "wildberries": ("wildberries.ru", "wb.ru"),
    "ozon": ("ozon.ru",),
    "yandex_market": ("market.yandex.ru",),
    "avito": ("avito.ru",),
    "aliexpress": ("aliexpress.com", "aliexpress.ru"),
    "kaspi": ("kaspi.kz",),
}

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
    }
)


def _normalize_hostname(hostname: str | None) -> str:
    """Нормализовать hostname (без порта, в нижнем регистре)."""
    if not hostname:
        return ""
    return hostname.strip().lower().rstrip(".")


def _hostname_is_blocked_ip(hostname: str) -> bool:
    """True, если hostname — loopback/private/link-local/reserved IP."""
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False

    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def assert_hostname_safe(hostname: str) -> None:
    """Запретить опасные hostname до сетевого запроса."""
    host = _normalize_hostname(hostname)
    if not host:
        raise UrlSecurityError("Некорректный URL товара")

    if host in _BLOCKED_HOSTNAMES:
        raise UrlSecurityError("Запрещённый адрес для парсинга")

    if _hostname_is_blocked_ip(host):
        raise UrlSecurityError("Запрещённый адрес для парсинга")


def host_matches_suffix(hostname: str, suffix: str) -> bool:
    """Проверить, что hostname равен suffix или является его поддоменом."""
    host = _normalize_hostname(hostname)
    suffix = suffix.lower().lstrip(".")
    return host == suffix or host.endswith(f".{suffix}")


def marketplace_from_hostname(hostname: str) -> str | None:
    """Определить маркетплейс только по hostname (не по path/query)."""
    assert_hostname_safe(hostname)
    host = _normalize_hostname(hostname)

    for marketplace, suffixes in MARKETPLACE_HOST_SUFFIXES.items():
        if any(host_matches_suffix(host, suffix) for suffix in suffixes):
            return marketplace

    return None


def validate_marketplace_product_url(url: str) -> tuple[str, str]:
    """
    Проверить URL товара для парсинга.

    Returns:
        (normalized_url, marketplace)

    Raises:
        ParserError: URL небезопасен или не поддерживается
    """
    if not url or not str(url).strip():
        raise UrlSecurityError("URL товара не указан")

    normalized_url = str(url).strip()
    parsed = urlparse(normalized_url)

    if parsed.scheme not in {"http", "https"}:
        raise UrlSecurityError("Некорректный URL товара")

    if parsed.username or parsed.password:
        raise UrlSecurityError("URL с учётными данными запрещён")

    hostname = parsed.hostname
    assert_hostname_safe(hostname or "")

    if parsed.port is not None and parsed.port not in {80, 443}:
        raise UrlSecurityError("Недопустимый порт в URL")

    marketplace = marketplace_from_hostname(hostname or "")
    if marketplace is None:
        raise UrlSecurityError("Неподдерживаемый маркетплейс")

    return normalized_url, marketplace
