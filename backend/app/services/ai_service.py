"""
AI-сервис для работы с языковыми моделями.

Поддерживает:
- Яндекс GPT (Yandex Cloud)
- DeepSeek API
- OpenAI API (опционально)

Используется для:
- Генерации SEO-названий товаров
- Анализа описаний конкурентов
- Создания характеристик товаров
- Классификации товаров по категориям
"""

import httpx
from typing import Optional, Dict, Any, List
from loguru import logger
from app.config import settings
import json
import re


class AIService:
    """
    Сервис для работы с AI-моделями.
    
    Поддерживает несколько провайдеров с автоматическим переключением.
    """
    
    def __init__(self):
        """Инициализация AI-сервиса."""
        self.yandex_api_key = settings.yandex_gpt_api_key
        self.yandex_folder_id = settings.yandex_cloud_folder_id
        self.deepseek_api_key = settings.deepseek_api_key
        self.openai_api_key = settings.openai_api_key
        
        # Логический «основной» провайдер (для совместимости со старым API).
        self.provider = self._detect_provider()

        # Последний реально использованный провайдер для запроса.
        self.last_used_provider = "none"

        logger.info(f"🤖 AI-провайдер (основной): {self.provider}")
    
    def _detect_provider(self) -> str:
        """
        Определение доступного AI-провайдера.
        
        Returns:
            str: Название провайдера (yandex, deepseek, openai, none)
        """
        if self.yandex_api_key and self.yandex_folder_id:
            return "yandex"
        elif self.deepseek_api_key:
            return "deepseek"
        elif self.openai_api_key:
            return "openai"
        else:
            return "none"
    
    async def _generate_text_with_fallback(self, system_prompt: str, prompt: str, fallback_text: str) -> str:
        """
        Унифицированный вызов AI с fallback между провайдерами.

        Логика приоритета:
        1) Яндекс GPT (если настроен)
        2) OpenAI (если настроен)
        3) DeepSeek (если настроен)

        Args:
            system_prompt: Системный промпт
            prompt: Пользовательский промпт
            fallback_text: Текст по умолчанию, если все провайдеры недоступны/упали

        Returns:
            str: Ответ модели или fallback_text
        """
        providers_chain = []

        if self.yandex_api_key and self.yandex_folder_id:
            providers_chain.append(("yandex", self._call_yandex_gpt))

        if self.openai_api_key:
            providers_chain.append(("openai", self._call_openai))

        if self.deepseek_api_key:
            providers_chain.append(("deepseek", self._call_deepseek))

        if not providers_chain:
            self.last_used_provider = "none"
            logger.warning("⚠️ AI-провайдеры не настроены, возвращаю fallback")
            return fallback_text

        for provider_name, provider_call in providers_chain:
            try:
                answer = await provider_call(system_prompt, prompt)
                if isinstance(answer, str) and answer.strip() and not answer.startswith("Ошибка"):
                    self.last_used_provider = provider_name
                    return answer.strip()

                logger.warning(
                    f"⚠️ Пустой/ошибочный ответ от {provider_name}, пробую следующий провайдер"
                )
            except Exception as error:
                logger.error(f"❌ Сбой провайдера {provider_name}: {error}")

        self.last_used_provider = "none"
        logger.error("❌ Все AI-провайдеры недоступны, возвращаю fallback")
        return fallback_text

    async def generate_seo_title(
        self,
        product_name: str,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        characteristics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Генерация SEO-оптимизированного названия товара.
        
        Args:
            product_name: Исходное название товара
            category: Категория товара
            brand: Бренд товара
            characteristics: Характеристики товара
            
        Returns:
            str: SEO-оптимизированное название
        """
        # Формируем промпт
        prompt = self._build_seo_prompt(product_name, category, brand, characteristics)
        
        # Системное сообщение
        system_prompt = """Ты — эксперт по SEO для маркетплейсов (Wildberries, Ozon).
Твоя задача — создавать продающие и оптимизированные названия товаров.

Правила хорошего названия:
1. Длина: 50-100 символов
2. Структура: [Бренд] + [Тип товара] + [Ключевые характеристики] + [Цвет/Размер]
3. Используй популярные поисковые запросы
4. Избегай спецсимволов и капса
5. Указывай важные для покупателя характеристики

Примеры хороших названий:
- Футболка мужская хлопковая базовая белая размер L
- Наушники беспроводные TWS с микрофоном и зарядным кейсом черные
- Лампа светодиодная настольная с регулировкой яркости 10W"""

        return await self._generate_text_with_fallback(
            system_prompt=system_prompt,
            prompt=prompt,
            fallback_text=product_name,
        )
    
    def _build_seo_prompt(
        self,
        product_name: str,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        characteristics: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Построение промпта для генерации SEO-названия.
        
        Args:
            product_name: Исходное название
            category: Категория
            brand: Бренд
            characteristics: Характеристики
            
        Returns:
            str: Промпт для AI
        """
        prompt = f"Создай SEO-оптимизированное название для товара:\n\n"
        prompt += f"Исходное название: {product_name}\n"
        
        if category:
            prompt += f"Категория: {category}\n"
        
        if brand:
            prompt += f"Бренд: {brand}\n"
        
        if characteristics:
            prompt += "Характеристики:\n"
            for key, value in list(characteristics.items())[:5]:  # Ограничиваем количество
                prompt += f"  - {key}: {value}\n"
        
        prompt += "\nВерни только название товара, без кавычек и пояснений."
        
        return prompt
    
    async def _call_yandex_gpt(self, system_prompt: str, user_prompt: str) -> str:
        """
        Вызов Яндекс GPT API.
        
        Args:
            system_prompt: Системное сообщение
            user_prompt: Пользовательский запрос
            
        Returns:
            str: Ответ модели
        """
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.yandex_api_key}",
            "x-folder-id": self.yandex_folder_id,
        }
        
        payload = {
            "modelUri": f"gpt://{self.yandex_folder_id}/yandexgpt/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": 200,
            },
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": user_prompt},
            ],
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                answer = result["result"]["alternatives"][0]["message"]["text"]
                
                logger.info(f"✅ Яндекс GPT ответил: {answer[:50]}...")
                return answer
                
        except httpx.HTTPError as e:
            logger.error(f"❌ Ошибка Яндекс GPT API: {e}")
            return f"Ошибка API: {e}"
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка Яндекс GPT: {e}")
            return f"Ошибка: {e}"
    
    async def _call_deepseek(self, system_prompt: str, user_prompt: str) -> str:
        """
        Вызов DeepSeek API.
        
        Args:
            system_prompt: Системное сообщение
            user_prompt: Пользовательский запрос
            
        Returns:
            str: Ответ модели
        """
        url = "https://api.deepseek.com/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_api_key}",
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 200,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                
                logger.info(f"✅ DeepSeek ответил: {answer[:50]}...")
                return answer
                
        except httpx.HTTPError as e:
            logger.error(f"❌ Ошибка DeepSeek API: {e}")
            return f"Ошибка API: {e}"
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка DeepSeek: {e}")
            return f"Ошибка: {e}"
    
    async def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        """
        Вызов OpenAI API.
        
        Args:
            system_prompt: Системное сообщение
            user_prompt: Пользовательский запрос
            
        Returns:
            str: Ответ модели
        """
        url = "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}",
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 200,
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                
                logger.info(f"✅ OpenAI ответил: {answer[:50]}...")
                return answer
                
        except httpx.HTTPError as e:
            logger.error(f"❌ Ошибка OpenAI API: {e}")
            return f"Ошибка API: {e}"
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка OpenAI: {e}")
            return f"Ошибка: {e}"
    
    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        n: int = 1,
        quality: str = "high",
    ) -> Dict[str, Any]:
        """
        Сгенерировать изображение(я) через OpenAI Images API (модель gpt-image-1).

        gpt-image-1 — самая мощная модель генерации изображений OpenAI,
        подходит для предметных фото и инфографики карточек.

        Args:
            prompt: Текстовое описание желаемого изображения
            size: Размер ("1024x1024", "1024x1536", "1536x1024")
            n: Количество вариантов (1-4)
            quality: Качество ("low", "medium", "high")

        Returns:
            Dict: {"status": "ok"|"not_configured"|"error", "images": [b64,...], "model": str, "message": str}
        """
        if not self.openai_api_key:
            return {
                "status": "not_configured",
                "images": [],
                "message": "OpenAI API ключ не настроен (нужен для генерации изображений)",
            }

        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-image-1",
            "prompt": prompt,
            "size": size,
            "n": max(1, min(int(n), 4)),
            "quality": quality,
        }

        try:
            # Генерация изображений может занимать заметное время — увеличиваем таймаут.
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

                data = response.json()
                images = [
                    item["b64_json"]
                    for item in data.get("data", [])
                    if item.get("b64_json")
                ]

                if not images:
                    return {"status": "error", "images": [], "message": "OpenAI не вернул изображения"}

                self.last_used_provider = "openai"
                logger.info(f"✅ OpenAI сгенерировал изображений: {len(images)}")
                return {"status": "ok", "images": images, "model": "gpt-image-1"}

        except httpx.HTTPStatusError as error:
            detail = error.response.text[:300] if error.response is not None else str(error)
            logger.error(f"❌ Ошибка OpenAI Images API: {error.response.status_code if error.response else '?'} {detail}")
            return {
                "status": "error",
                "images": [],
                "message": f"OpenAI вернул ошибку при генерации изображения",
            }
        except Exception as error:
            logger.error(f"❌ Неожиданная ошибка генерации изображения: {error}")
            return {"status": "error", "images": [], "message": "Ошибка генерации изображения"}

    async def answer_review(
        self,
        product_name: str,
        review_text: str,
        rating: Optional[float] = None,
        is_question: bool = False,
    ) -> str:
        """
        Сгенерировать ответ продавца на отзыв или вопрос покупателя.

        Args:
            product_name: Название товара
            review_text: Текст отзыва/вопроса покупателя
            rating: Оценка (для отзыва), 1-5
            is_question: True если это вопрос, а не отзыв

        Returns:
            str: Готовый ответ для публикации
        """
        kind = "вопрос" if is_question else "отзыв"
        rating_note = f"\nОценка покупателя: {rating} из 5." if rating is not None else ""

        system_prompt = (
            "Ты — менеджер магазина на маркетплейсе. Пиши вежливые, человечные и краткие "
            "ответы на отзывы и вопросы покупателей на русском языке. "
            "Правила: поблагодари за обратную связь; если отзыв негативный — извинись и предложи решение; "
            "не используй шаблонные канцеляризмы и эмодзи; 2–4 предложения; не обещай того, что не зависит от продавца."
        )
        prompt = (
            f"Товар: {product_name}\n"
            f"Тип обращения: {kind}.{rating_note}\n"
            f"Текст покупателя: {review_text}\n\n"
            "Напиши ответ продавца. Верни только текст ответа без кавычек."
        )

        fallback = (
            "Благодарим за обратную связь! Нам важно ваше мнение. "
            "Если возникли вопросы по товару — напишите нам, и мы поможем решить ситуацию."
        )
        return await self._generate_text_with_fallback(
            system_prompt=system_prompt, prompt=prompt, fallback_text=fallback
        )

    async def widget_assistant_reply(
        self,
        store_title: str,
        products_context: str,
        history: List[Dict[str, str]],
        message: str,
    ) -> str:
        """
        Сгенерировать ответ ассистента-консультанта виджета на сайте продавца.

        Args:
            store_title: Название магазина/виджета
            products_context: Краткий список товаров продавца как контекст
            history: История диалога [{role: "user"|"assistant", text: str}]
            message: Новое сообщение посетителя

        Returns:
            str: Ответ ассистента
        """
        system_prompt = (
            f"Ты — вежливый AI-консультант интернет-магазина «{store_title}». "
            "Помогаешь посетителям выбрать товар и отвечаешь на вопросы кратко и по делу, на русском. "
            "Опирайся на список товаров магазина, если он есть. Не выдумывай товары, которых нет. "
            "Если не знаешь — предложи связаться с продавцом. 1–4 предложения."
        )

        # Сворачиваем историю и контекст в единый промпт.
        dialog_lines = []
        for turn in history[-8:]:
            role = "Покупатель" if turn.get("role") == "user" else "Ассистент"
            text = str(turn.get("text", "")).strip()
            if text:
                dialog_lines.append(f"{role}: {text[:500]}")

        prompt_parts = []
        if products_context:
            prompt_parts.append(f"Товары магазина:\n{products_context}")
        if dialog_lines:
            prompt_parts.append("История диалога:\n" + "\n".join(dialog_lines))
        prompt_parts.append(f"Новое сообщение покупателя: {message}\n\nОтветь как консультант.")
        prompt = "\n\n".join(prompt_parts)

        fallback = (
            "Спасибо за обращение! Уточните, пожалуйста, что именно вы ищете, "
            "и я подскажу подходящий товар. Также вы можете связаться с продавцом напрямую."
        )
        return await self._generate_text_with_fallback(
            system_prompt=system_prompt, prompt=prompt, fallback_text=fallback
        )

    async def generate_seo_keywords(
        self,
        product_name: str,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Подобрать и кластеризовать поисковые ключи для карточки.

        Returns:
            Dict: {"keywords": [...], "clusters": {cluster: [...]}, "provider": str}
        """
        system_prompt = (
            "Ты — SEO-специалист по маркетплейсам. Подбирай реальные поисковые запросы "
            "покупателей и группируй их по смысловым кластерам. Отвечай ТОЛЬКО JSON."
        )
        prompt = (
            f"Товар: {product_name}\n"
            f"Категория: {category or 'не указана'}\n\n"
            "Верни JSON вида:\n"
            '{"keywords": ["ключ1", "ключ2"], '
            '"clusters": {"Название кластера": ["ключ1", "ключ2"]}}\n'
            "Дай 15-30 ключей и 3-6 кластеров."
        )

        response = await self._generate_text_with_fallback(
            system_prompt=system_prompt, prompt=prompt, fallback_text="{}"
        )

        keywords: List[str] = []
        clusters: Dict[str, List[str]] = {}
        parsed = self._safe_json(response)
        if isinstance(parsed, dict):
            raw_keywords = parsed.get("keywords")
            if isinstance(raw_keywords, list):
                keywords = [str(k).strip()[:100] for k in raw_keywords[:50] if str(k).strip()]
            raw_clusters = parsed.get("clusters")
            if isinstance(raw_clusters, dict):
                for name, items in list(raw_clusters.items())[:10]:
                    if isinstance(items, list):
                        clusters[str(name)[:100]] = [
                            str(i).strip()[:100] for i in items[:30] if str(i).strip()
                        ]

        return {
            "keywords": keywords,
            "clusters": clusters,
            "provider": self.last_used_provider,
        }

    async def audit_sku(
        self,
        product_name: str,
        description: Optional[str] = None,
        characteristics: Optional[Dict[str, Any]] = None,
        images_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Провести аудит карточки товара и вернуть оценку с рекомендациями.

        Returns:
            Dict: {"score": int, "issues": [...], "recommendations": [...], "provider": str}
        """
        chars_str = ""
        if characteristics:
            chars_str = "; ".join(f"{k}: {v}" for k, v in list(characteristics.items())[:15])

        system_prompt = (
            "Ты — эксперт по карточкам товаров на Wildberries и Ozon. "
            "Оцени качество карточки и дай конкретные улучшения. Отвечай ТОЛЬКО JSON."
        )
        prompt = (
            f"Название: {product_name}\n"
            f"Описание: {(description or '')[:1500]}\n"
            f"Характеристики: {chars_str or 'не заданы'}\n"
            f"Количество фото: {images_count}\n\n"
            "Верни JSON: {\"score\": 0-100, \"issues\": [\"проблема\"], "
            "\"recommendations\": [\"рекомендация\"]}"
        )

        response = await self._generate_text_with_fallback(
            system_prompt=system_prompt, prompt=prompt, fallback_text="{}"
        )

        parsed = self._safe_json(response)
        score = 0
        issues: List[str] = []
        recommendations: List[str] = []
        if isinstance(parsed, dict):
            raw_score = parsed.get("score")
            if isinstance(raw_score, (int, float)):
                score = max(0, min(100, int(raw_score)))
            if isinstance(parsed.get("issues"), list):
                issues = [str(i).strip()[:300] for i in parsed["issues"][:10] if str(i).strip()]
            if isinstance(parsed.get("recommendations"), list):
                recommendations = [
                    str(r).strip()[:300] for r in parsed["recommendations"][:10] if str(r).strip()
                ]

        # Базовая эвристика, если AI недоступен/не дал оценку.
        if score == 0 and not issues:
            heuristic_score = 50
            if description and len(description) > 300:
                heuristic_score += 15
            if characteristics and len(characteristics) >= 5:
                heuristic_score += 15
            if images_count >= 5:
                heuristic_score += 15
            score = min(heuristic_score, 95)
            if images_count < 5:
                recommendations.append("Добавьте больше фото (рекомендуется 5+).")
            if not description or len(description) < 300:
                recommendations.append("Расширьте описание до 500+ символов с ключевыми словами.")

        return {
            "score": score,
            "issues": issues,
            "recommendations": recommendations,
            "provider": self.last_used_provider,
        }

    def _safe_json(self, response: str) -> Optional[Any]:
        """Безопасно распарсить JSON из ответа модели (с извлечением блока {...})."""
        if not response:
            return None
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response, flags=re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    async def analyze_competitors(
        self,
        product_name: str,
        competitor_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        AI-анализ конкурентов.
        
        Args:
            product_name: Название товара
            competitor_data: Список данных о конкурентах
            
        Returns:
            Dict с результатами анализа
        """
        baseline_analysis = self._build_rule_based_competitor_analysis(competitor_data)

        if not competitor_data:
            return baseline_analysis

        # Формируем промпт только по валидированным данным без лишнего payload.
        competitors_str = "\n".join([
            f"- {c.get('name', 'N/A')}: {c.get('price', 0)} руб. (рейтинг: {c.get('rating', 0)})"
            for c in competitor_data[:10]
        ])
        
        prompt = f"""Товар: {product_name}

Конкуренты:
{competitors_str}

Проанализируй и верни JSON:
{{
    "min_price": минимальная цена,
    "max_price": максимальная цена,
    "avg_price": средняя цена,
    "recommended_price": рекомендованная цена,
    "price_position": "дешевле" | "средняя" | "дороже",
    "recommendations": ["совет 1", "совет 2"]
}}"""
        
        system_prompt = "Ты — аналитик маркетплейсов. Отвечай ТОЛЬКО в формате JSON."
        
        if not (self.yandex_api_key and self.yandex_folder_id) and not self.openai_api_key and not self.deepseek_api_key:
            baseline_analysis["ai_status"] = "not_configured"
            baseline_analysis["provider_used"] = "none"
            return baseline_analysis
        
        response = await self._generate_text_with_fallback(
            system_prompt=system_prompt,
            prompt=prompt,
            fallback_text="{}",
        )

        parsed_analysis = self._parse_competitor_ai_response(response)
        if not parsed_analysis:
            baseline_analysis["ai_status"] = "fallback_invalid_ai_response"
            baseline_analysis["provider_used"] = self.last_used_provider
            return baseline_analysis

        merged_analysis = {**baseline_analysis, **parsed_analysis}
        merged_analysis["ai_status"] = "ok"
        merged_analysis["provider_used"] = self.last_used_provider
        merged_analysis["competitors_count"] = len(competitor_data)
        return merged_analysis

    def _build_rule_based_competitor_analysis(self, competitor_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Сделать стабильный расчёт анализа без зависимости от AI-провайдера."""
        prices = [
            float(item.get("price"))
            for item in competitor_data
            if isinstance(item.get("price"), (int, float)) and float(item.get("price")) > 0
        ]

        if not prices:
            return {
                "min_price": None,
                "max_price": None,
                "avg_price": None,
                "recommended_price": None,
                "price_position": "unknown",
                "recommendations": ["Добавьте конкурентов с валидной ценой для анализа."],
                "competitors_count": len(competitor_data),
                "provider_used": "none",
                "ai_status": "no_valid_prices",
            }

        min_price = min(prices)
        max_price = max(prices)
        avg_price = round(sum(prices) / len(prices), 2)
        recommended_price = round(max(min_price * 0.98, avg_price * 0.9), 2)

        return {
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": avg_price,
            "recommended_price": recommended_price,
            "price_position": "средняя",
            "recommendations": [
                "Используйте рекомендованную цену как безопасную стартовую точку.",
                "Проверьте маржинальность перед применением репрайсинга.",
            ],
            "competitors_count": len(competitor_data),
            "provider_used": "rule_based",
            "ai_status": "fallback_rule_based",
        }

    def _parse_competitor_ai_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Распарсить JSON из ответа модели и сохранить только ожидаемые поля."""
        if not response:
            return None

        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response, flags=re.DOTALL)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

        if not isinstance(parsed, dict):
            return None

        numeric_fields = ["min_price", "max_price", "avg_price", "recommended_price"]
        sanitized: Dict[str, Any] = {}
        for field in numeric_fields:
            value = parsed.get(field)
            if isinstance(value, (int, float)) and value > 0:
                sanitized[field] = round(float(value), 2)

        price_position = parsed.get("price_position")
        if isinstance(price_position, str) and price_position.strip():
            sanitized["price_position"] = price_position.strip()[:50]

        recommendations = parsed.get("recommendations")
        if isinstance(recommendations, list):
            sanitized["recommendations"] = [
                str(item).strip()[:300]
                for item in recommendations[:5]
                if str(item).strip()
            ]

        return sanitized or None


# Глобальный экземпляр сервиса (ленивая инициализация)
_ai_service_instance = None


def get_ai_service() -> AIService:
    """Получение экземпляра AI-сервиса."""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance


# Для обратной совместимости
ai_service = get_ai_service()
