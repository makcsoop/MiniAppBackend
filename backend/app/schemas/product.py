# app/schemas/product.py
from __future__ import annotations  # 👈 Обязательно для отложенных аннотаций

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

# Импортируем только для type-checking, чтобы избежать циклического импорта
if TYPE_CHECKING:
    from app.schemas.category import CategoryResponse

from app.models.product import ProductType, ProductStatus


class ProductBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., pattern=r'^[a-z0-9\-]+$')
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    currency: str = Field(default="RUB", pattern=r'^[A-Z]{3}$')
    product_type: ProductType = ProductType.SERVICE
    image_url: Optional[str] = None
    gallery: Optional[List[str]] = None  # 👈 List[str], а не list[str]
    category_id: Optional[int] = None
    is_featured: bool = False
    sort_order: int = 0

    @field_validator('price')
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Цена должна быть больше 0')
        return round(v, 2)


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    gallery: Optional[List[str]] = None
    category_id: Optional[int] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None
    status: Optional[ProductStatus] = None


class ProductResponse(ProductBase):
    id: int
    status: ProductStatus
    # 👇 Forward reference в кавычках + полный путь для rebuild
    category: Optional['CategoryResponse'] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductOut(BaseModel):
    id: int
    title: str
    slug: str
    description: str | None = None
    price: float
    currency: str
    image_url: str | None = None
    product_type: str
    status: str
    category_id: int | None = None
    
    model_config = ConfigDict(from_attributes=True)


def _rebuild_product_schemas():
    """Rebuild schemas с явным указанием типов для циклических ссылок"""
    try:
        from app.schemas.category import CategoryResponse
        ProductResponse.model_rebuild(_types_namespace={'CategoryResponse': CategoryResponse})
    except ImportError:
        ProductResponse.model_rebuild(_types_namespace={})

if not TYPE_CHECKING:
    _rebuild_product_schemas()