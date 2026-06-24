"""Тест парсинга через API."""
import asyncio
from app.services.parser_service import parse_wildberries_sync
from app.services.cache_service import cache_service


async def test():
    print("Тест 1: Парсер")
    data = parse_wildberries_sync("https://www.wildberries.ru/catalog/24319630/detail.aspx")
    print(f"  Данные получены: {data is not None}")
    print(f"  Название: {data.get('name') if data else 'N/A'}")
    print(f"  Цена: {data.get('price') if data else 'N/A'}")
    
    print("\nТест 2: Кэш")
    try:
        cached = await cache_service.get_parsed_product("test_url")
        print(f"  Кэш работает: {cached is None}")  # None = нет в кэше, это нормально
    except Exception as e:
        print(f"  Ошибка кэша: {e}")


if __name__ == "__main__":
    asyncio.run(test())
