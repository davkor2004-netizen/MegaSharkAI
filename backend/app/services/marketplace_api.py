"""
Сервис для проверки API ключей маркетплейсов.
Проверяет валидность ключа через API маркетплейса.
"""

import httpx
from loguru import logger
from typing import Optional


class MarketplaceAPIService:
    """
    Сервис для работы с API маркетплейсов.
    """
    
    # URL API маркетплейсов
    MARKETPLACE_APIS = {
        "wildberries": {
            "name": "Wildberries",
            "check_url": "https://statistics-api.wildberries.ru/api/v1/supplier/orders",
            "header_name": "Authorization",
            "header_prefix": "",  # Ключ передаётся как есть
        },
        "ozon": {
            "name": "Ozon",
            "check_url": "https://api-seller.ozon.ru/v3/posting/fbs/unfulfilled/list",
            "header_name": "Api-Key",
            "header_prefix": "",
        },
        "yandex_market": {
            "name": "Яндекс Маркет",
            "check_url": "https://api.partner.market.yandex.ru/v2/campaigns",
            "header_name": "Authorization",
            "header_prefix": "OAuth ",
        },
        "avito": {
            "name": "Avito",
            "check_url": "https://api.avito.ru/profile/v1/user",
            "header_name": "Authorization",
            "header_prefix": "Bearer ",
        },
    }
    
    async def check_api_key(
        self,
        marketplace: str,
        api_key: str,
        additional_credentials: Optional[dict] = None,
    ) -> bool:
        """
        Проверка валидности API ключа.
        
        Args:
            marketplace: Название маркетплейса
            api_key: API ключ для проверки
            
        Returns:
            bool: True если ключ валиден
        """
        if marketplace not in self.MARKETPLACE_APIS:
            logger.warning(f"Неизвестный маркетплейс: {marketplace}")
            return False
        
        config = self.MARKETPLACE_APIS[marketplace]
        
        # Специальная обработка для Avito - у них нет публичного API для обычных селлеров
        if marketplace == "avito":
            # Для Avito просто проверяем формат ключа (если это токен)
            # или считаем валидным если ключ не пустой (для ручного ввода)
            logger.info("Avito: проверка ключа упрощённая (нет публичного API)")
            return bool(api_key and len(api_key) > 10)
        
        headers = self.build_headers(marketplace, api_key, additional_credentials)
        if headers is None:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if marketplace == "ozon":
                    response = await client.post(
                        config["check_url"],
                        headers=headers,
                        json={"dir": "ASC", "filter": {}, "limit": 1, "offset": 0},
                    )
                else:
                    response = await client.get(config["check_url"], headers=headers)
                
                # Wildberries возвращает 200 даже при пустом ответе
                if marketplace == "wildberries":
                    # 401 или 403 - неверный ключ
                    if response.status_code in [401, 403]:
                        logger.warning(f"Wildberries: неверный API ключ")
                        return False
                    # 200 - ключ валиден
                    logger.info(f"Wildberries: ключ валиден")
                    return True
                
                # Ozon
                elif marketplace == "ozon":
                    if response.status_code == 200:
                        logger.info(f"Ozon: ключ валиден")
                        return True
                    else:
                        logger.warning(f"Ozon: неверный API ключ (статус {response.status_code})")
                        return False
                
                # Яндекс Маркет
                elif marketplace == "yandex_market":
                    if response.status_code == 200:
                        logger.info(f"Яндекс Маркет: ключ валиден")
                        return True
                    else:
                        logger.warning(f"Яндекс Маркет: неверный API ключ (статус {response.status_code})")
                        return False
                
                return False
                
        except httpx.TimeoutException:
            logger.warning(f"Таймаут при проверке ключа {marketplace}")
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки ключа {marketplace}: {e}")
            return False
    
    def build_headers(
        self,
        marketplace: str,
        api_key: str,
        additional_credentials: Optional[dict] = None,
    ) -> Optional[dict]:
        """Собрать headers для marketplace API без логирования секретов."""
        if marketplace not in self.MARKETPLACE_APIS:
            return None

        config = self.MARKETPLACE_APIS[marketplace]
        headers = {
            config["header_name"]: f"{config['header_prefix']}{api_key}",
            "Content-Type": "application/json",
        }

        if marketplace == "ozon":
            client_id = (additional_credentials or {}).get("client_id")
            if not client_id:
                logger.warning("Ozon: отсутствует Client-Id")
                return None
            headers["Client-Id"] = str(client_id)

        return headers

    async def get_wildberries_products(self, api_key: str, product_id: str = None):
        """
        Получение списка товаров из Wildberries.
        
        Args:
            api_key: API ключ Wildberries
            product_id: Артикул товара (необязательно)
            
        Returns:
            list: Список товаров
        """
        # Wildberries Statistics API
        url = "https://statistics-api.wildberries.ru/api/v2/supplier/products"
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Преобразуем в удобный формат
                    products = []
                    if isinstance(data, list):
                        for item in data:
                            product = {
                                "external_id": str(item.get("nmID", "")),
                                "name": item.get("name", ""),
                                "price": item.get("price", 0),
                                "quantity": item.get("quantity", 0),
                                "category": item.get("subjectName", ""),
                                "brand": item.get("brand", ""),
                                "vendor_code": item.get("vendorCode", ""),
                                "marketplace": "wildberries",
                            }
                            products.append(product)
                    
                    # Если указан product_id, фильтруем
                    if product_id:
                        products = [p for p in products if p["external_id"] == product_id]
                    
                    return products
                else:
                    logger.error(f"Wildberries API error: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка получения товаров WB: {e}")
            return []
    
    async def get_ozon_products(
        self,
        api_key: str,
        product_id: str = None,
        additional_credentials: Optional[dict] = None,
    ):
        """
        Получение списка товаров из Ozon.
        
        Args:
            api_key: API ключ Ozon
            product_id: Артикул товара (необязательно)
            
        Returns:
            list: Список товаров
        """
        url = "https://api-seller.ozon.ru/v3/product/list"
        headers = self.build_headers("ozon", api_key, additional_credentials)
        if headers is None:
            logger.warning("Ozon: товары не запрошены, потому что Client-Id не настроен")
            return []
        
        body = {
            "limit": 100,
            "last_id": "",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=body)
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    items = result.get("items", [])
                    
                    # Преобразуем в удобный формат
                    products = []
                    for item in items:
                        product = {
                            "external_id": str(item.get("product_id", "")),
                            "name": item.get("name", ""),
                            "price": item.get("price", 0),
                            "quantity": item.get("quantity", 0),
                            "category": "",
                            "brand": "",
                            "vendor_code": item.get("offer_id", ""),
                            "marketplace": "ozon",
                        }
                        products.append(product)
                    
                    # Если указан product_id, фильтруем
                    if product_id:
                        products = [p for p in products if p["external_id"] == product_id]
                    
                    return products
                else:
                    logger.error(f"Ozon API error: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка получения товаров Ozon: {e}")
            return []
    
    async def update_price(
        self,
        marketplace: str,
        api_key: str,
        external_id: str,
        price: float,
        old_price: Optional[float] = None,
        additional_credentials: Optional[dict] = None,
    ) -> dict:
        """
        Применить новую цену товара на маркетплейсе.

        Единая точка входа: по названию маркетплейса вызывает нужный метод.

        Returns:
            dict: {"status": "applied"|"error"|"not_supported", "message": str}
        """
        marketplace = (marketplace or "").lower()

        if marketplace == "wildberries":
            return await self.update_wildberries_price(api_key, external_id, price)

        if marketplace == "ozon":
            return await self.update_ozon_price(
                api_key, external_id, price, old_price, additional_credentials
            )

        # Яндекс Маркет и Avito пока без реальной интеграции записи цены.
        logger.warning(f"Обновление цены не поддержано для маркетплейса: {marketplace}")
        return {
            "status": "not_supported",
            "message": f"Применение цены для {marketplace or 'unknown'} пока не поддерживается",
        }

    async def update_wildberries_price(
        self,
        api_key: str,
        external_id: str,
        price: float,
    ) -> dict:
        """
        Обновить цену товара на Wildberries.

        Используется Discounts-Prices API:
        POST https://discounts-prices-api.wildberries.ru/api/v2/upload/task
        Тело: {"data": [{"nmID": <int>, "price": <int>}]}
        """
        try:
            nm_id = int(str(external_id).strip())
        except (TypeError, ValueError):
            return {"status": "error", "message": "Некорректный nmID товара Wildberries"}

        url = "https://discounts-prices-api.wildberries.ru/api/v2/upload/task"
        headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        body = {"data": [{"nmID": nm_id, "price": int(round(price))}]}

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json=body)

            if response.status_code in (200, 208):
                logger.info(f"✅ WB: цена товара {nm_id} отправлена ({int(round(price))} ₽)")
                return {"status": "applied", "message": "Цена отправлена в Wildberries"}

            if response.status_code in (401, 403):
                return {"status": "error", "message": "Неверный или недействительный API-ключ Wildberries"}

            logger.error(f"❌ WB price update error: {response.status_code} {response.text[:200]}")
            return {"status": "error", "message": f"Wildberries вернул статус {response.status_code}"}
        except httpx.TimeoutException:
            return {"status": "error", "message": "Таймаут запроса к Wildberries"}
        except Exception as error:
            logger.error(f"❌ Ошибка обновления цены WB: {error}")
            return {"status": "error", "message": "Ошибка обновления цены Wildberries"}

    async def update_ozon_price(
        self,
        api_key: str,
        external_id: str,
        price: float,
        old_price: Optional[float] = None,
        additional_credentials: Optional[dict] = None,
    ) -> dict:
        """
        Обновить цену товара на Ozon.

        POST https://api-seller.ozon.ru/v1/product/import/prices
        Тело: {"prices": [{"product_id": <int>, "price": "<str>", "old_price": "<str>"}]}
        """
        headers = self.build_headers("ozon", api_key, additional_credentials)
        if headers is None:
            return {"status": "error", "message": "Для Ozon не настроен Client-Id"}

        try:
            product_id = int(str(external_id).strip())
        except (TypeError, ValueError):
            return {"status": "error", "message": "Некорректный product_id товара Ozon"}

        price_item = {
            "product_id": product_id,
            "price": str(int(round(price))),
            "old_price": str(int(round(old_price))) if old_price else "0",
        }
        url = "https://api-seller.ozon.ru/v1/product/import/prices"
        body = {"prices": [price_item]}

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json=body)

            if response.status_code == 200:
                data = response.json()
                results = data.get("result", [])
                if results and not results[0].get("updated", True):
                    errors = results[0].get("errors", [])
                    message = errors[0].get("message") if errors else "Ozon отклонил обновление цены"
                    return {"status": "error", "message": message}

                logger.info(f"✅ Ozon: цена товара {product_id} отправлена ({int(round(price))} ₽)")
                return {"status": "applied", "message": "Цена отправлена в Ozon"}

            if response.status_code in (401, 403):
                return {"status": "error", "message": "Неверный или недействительный API-ключ Ozon"}

            logger.error(f"❌ Ozon price update error: {response.status_code} {response.text[:200]}")
            return {"status": "error", "message": f"Ozon вернул статус {response.status_code}"}
        except httpx.TimeoutException:
            return {"status": "error", "message": "Таймаут запроса к Ozon"}
        except Exception as error:
            logger.error(f"❌ Ошибка обновления цены Ozon: {error}")
            return {"status": "error", "message": "Ошибка обновления цены Ozon"}

    async def get_yandex_products(self, api_key: str, product_id: str = None):
        """
        Получение списка товаров из Яндекс Маркета.
        
        Args:
            api_key: OAuth токен Яндекс Маркета
            product_id: SKU товара (необязательно)
            
        Returns:
            list: Список товаров
        """
        url = "https://api.partner.market.yandex.ru/v2/campaigns"
        headers = {
            "Authorization": f"OAuth {api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    # Возвращаем список кампаний (магазинов)
                    # Для получения товаров нужно делать дополнительный запрос
                    return data.get("result", {}).get("campaigns", [])
                else:
                    logger.error(f"Yandex Market API error: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Ошибка получения товаров Yandex Market: {e}")
            return []


# Глобальный экземпляр сервиса
marketplace_api_service = MarketplaceAPIService()
