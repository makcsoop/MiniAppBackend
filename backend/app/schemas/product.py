# app/schemas/product.py
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, List
from app.models.product import ProductType, ProductStatus
from app.schemas.category import CategoryResponse


class ProductBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., pattern=r'^[a-z0-9\-]+$')
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    currency: str = Field(default="RUB", pattern=r'^[A-Z]{3}$')
    product_type: ProductType = ProductType.SERVICE
    image_url: Optional[str] = None
    gallery: Optional[List[str]] = None
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
    category: Optional[CategoryResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductOut(BaseModel):
    id: int
    title: str
    slug: str
    description: Optional[str] = None
    price: float
    currency: str
    image_url: Optional[str] = None
    product_type: str
    status: str
    category_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)