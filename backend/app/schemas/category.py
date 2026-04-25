# app/schemas/category.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.product import ProductResponse


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    slug: str = Field(..., pattern=r'^[a-z0-9\-]+$')
    description: Optional[str] = Field(None, max_length=200)
    icon_url: Optional[str] = None
    sort_order: int = 0


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    product_count: int = 0  # Вычисляемое поле

    model_config = ConfigDict(from_attributes=True)


def _rebuild_category_schemas():
    try:
        from app.schemas.product import ProductResponse
        CategoryResponse.model_rebuild(_types_namespace={'ProductResponse': ProductResponse})
    except ImportError:
        CategoryResponse.model_rebuild(_types_namespace={})

if not TYPE_CHECKING:
    _rebuild_category_schemas()