"""
Модель товара для хранения данных о продуктах с маркетплейсов.

Используется для:
- Хранения собственных товаров пользователя
- Хранения данных о товарах конкурентов
- AI-анализа и сравнения
"""

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, JSON, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid

from app.models.base import BaseModel


class Product(BaseModel):
    """
    Модель товара на маркетплейсе.
    
    Атрибуты:
        id: Уникальный идентификатор
        external_id: ID товара на маркетплейсе (WB, Ozon и т.д.)
        marketplace: Название маркетплейса (wildberries, ozon, avito, kazanexpress, yandex_market)
        name: Название товара
        description: Полное описание товара
        price: Текущая цена товара
        old_price: Старая цена (до скидки)
        discount: Размер скидки в процентах
        rating: Рейтинг товара (0-5)
        reviews_count: Количество отзывов
        sales_count: Количество продаж
        category: Категория товара
        brand: Бренд товара
        images: JSON-массив ссылок на изображения
        characteristics: JSON-объект с характеристиками товара
        is_competitor: Флаг конкурента (True) или собственного товара (False)
        user_id: ID владельца (для собственных товаров)
        url: Ссылка на товар
        last_parsed_at: Время последнего парсинга
        vector_embedding: Векторное представление для AI-поиска (pgvector)
    """
    
    __tablename__ = "products"
    
    # ====================
    # Основные поля
    # ====================
    external_id = Column(
        String(100),
        nullable=True,
        index=True,
        comment="ID товара на маркетплейсе",
    )
    
    marketplace = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Название маркетплейса",
    )
    
    name = Column(
        Text,
        nullable=False,
        comment="Название товара",
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Описание товара",
    )
    
    # ====================
    # Цена и скидки
    # ====================
    price = Column(
        Float,
        nullable=True,  # Изменено: может быть NULL если парсинг не удался
        comment="Текущая цена",
    )
    
    old_price = Column(
        Float,
        nullable=True,
        comment="Старая цена до скидки",
    )
    
    discount = Column(
        Float,
        nullable=True,
        comment="Размер скидки в %",
    )
    
    # ====================
    # Рейтинги и продажи
    # ====================
    rating = Column(
        Float,
        nullable=True,
        comment="Рейтинг товара (0-5)",
    )
    
    reviews_count = Column(
        Integer,
        default=0,
        comment="Количество отзывов",
    )
    
    sales_count = Column(
        Integer,
        default=0,
        comment="Количество продаж",
    )
    
    # ====================
    # Категоризация
    # ====================
    category = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Категория товара",
    )
    
    brand = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Бренд товара",
    )
    
    # ====================
    # Медиа и характеристики
    # ====================
    images = Column(
        JSON,
        nullable=True,
        comment="Массив ссылок на изображения",
    )
    
    characteristics = Column(
        JSON,
        nullable=True,
        comment="Характеристики товара",
    )
    
    # ====================
    # Тип товара
    # ====================
    is_competitor = Column(
        Boolean,
        default=False,
        index=True,
        comment="Флаг конкурента",
    )
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="ID владельца товара",
    )
    
    # ====================
    # URL и парсинг
    # ====================
    url = Column(
        String(1000),
        nullable=True,
        comment="Ссылка на товар",
    )
    
    last_parsed_at = Column(
        DateTime,
        nullable=True,
        comment="Время последнего парсинга",
    )
    
    # ====================
    # AI векторное представление (pgvector)
    # ====================
    vector_embedding = Column(
        Vector(768),  # Размерность вектора для AI-эмбеддингов
        nullable=True,
        comment="Векторное представление для AI-поиска",
    )
    
    # ====================
    # Индексы
    # ====================
    __table_args__ = (
        Index("ix_products_user_marketplace_external_id", "user_id", "marketplace", "external_id", unique=True),
        Index("ix_products_user_is_competitor", "user_id", "is_competitor"),
        Index("ix_products_vector", "vector_embedding", postgresql_using="ivfflat"),
    )
    
    # ====================
    # Отношения
    # ====================
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    competitor_analysis = relationship("CompetitorAnalysis", back_populates="product", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name='{self.name[:50]}...', price={self.price})>"


class PriceHistory(BaseModel):
    """
    История изменения цен товара.
    
    Используется для:
    - Анализа динамики цен
    - Определения оптимального времени для репрайсинга
    - Отслеживания акций конкурентов
    """
    
    __tablename__ = "price_history"
    
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID товара",
    )
    
    price = Column(
        Float,
        nullable=False,
        comment="Цена на момент записи",
    )
    
    old_price = Column(
        Float,
        nullable=True,
        comment="Старая цена",
    )
    
    discount = Column(
        Float,
        nullable=True,
        comment="Размер скидки в %",
    )
    
    # Отношения
    product = relationship("Product", back_populates="price_history")
    
    __table_args__ = (
        Index("ix_price_history_product_created", "product_id", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<PriceHistory(product_id={self.product_id}, price={self.price})>"


class CompetitorAnalysis(BaseModel):
    """
    Результаты анализа конкурентов для товара.
    
    Хранит данные о позиционировании товара относительно конкурентов.
    """
    
    __tablename__ = "competitor_analyses"
    
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID анализируемого товара",
    )
    
    # Позиция среди конкурентов
    price_position = Column(
        String(20),
        nullable=True,
        comment="Позиция по цене (min, avg, max)",
    )
    
    min_competitor_price = Column(
        Float,
        nullable=True,
        comment="Минимальная цена конкурента",
    )
    
    avg_competitor_price = Column(
        Float,
        nullable=True,
        comment="Средняя цена конкурентов",
    )
    
    max_competitor_price = Column(
        Float,
        nullable=True,
        comment="Максимальная цена конкурента",
    )
    
    recommended_price = Column(
        Float,
        nullable=True,
        comment="Рекомендованная цена",
    )
    
    repricing_strategy = Column(
        String(50),
        nullable=True,
        comment="Стратегия репрайсинга",
    )
    
    analysis_data = Column(
        JSON,
        nullable=True,
        comment="Дополнительные данные анализа",
    )
    
    # Отношения
    product = relationship("Product", back_populates="competitor_analysis")
    
    def __repr__(self) -> str:
        return f"<CompetitorAnalysis(product_id={self.product_id}, recommended_price={self.recommended_price})>"
