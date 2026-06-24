import asyncio
from app.services.parser_service import parse_wildberries_async


async def main():
    print("Запуск парсера...")
    result = await parse_wildberries_async("https://www.wildberries.ru/catalog/24319630/detail.aspx")
    if result:
        print(f"✅ УСПЕХ!")
        print(f"  Название: {result.get('name')}")
        print(f"  Цена: {result.get('price')}")
        print(f"  Артикул: {result.get('external_id')}")
    else:
        print("❌ Парсер вернул None")


if __name__ == "__main__":
    asyncio.run(main())
