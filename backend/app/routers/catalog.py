from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.dependencies import get_db_session, get_current_user, get_catalog_service
from app.models.product import ProductType, ProductStatus
from app.models.user import User, UserRole
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.schemas.category import CategoryResponse, CategoryCreate, CategoryUpdate
from app.services.catalog import CatalogService

router = APIRouter(prefix="/catalog", tags=["Catalog"])

# === Публичные эндпоинты (без авторизации) ===

@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(
    only_active: bool = Query(True),
    service: CatalogService = Depends(get_catalog_service)
):
    """Получить список категорий"""
    return await service.get_categories(only_active=only_active)

@router.get("/products", response_model=dict)
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = Query(None),
    product_type: Optional[ProductType] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None, min_length=2),
    service: CatalogService = Depends(get_catalog_service)
):
    """Получить список продуктов с пагинацией и фильтрами"""
    products, total = await service.get_products(
        skip=skip, limit=limit,
        category_slug=category,
        product_type=product_type,
        min_price=min_price, max_price=max_price,
        search=search
    )
    return {
        "items": products,
        "total": total,
        "page": skip // limit + 1,
        "pages": (total + limit - 1) // limit,
        "has_next": skip + limit < total
    }

@router.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    service: CatalogService = Depends(get_catalog_service)
):
    """Получить детальную информацию о продукте"""
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# === Админские эндпоинты (только для role=admin) ===

@router.post("/admin/products", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    current_user: User = Depends(get_current_user),
    service: CatalogService = Depends(get_catalog_service)
):
    """Создать продукт (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await service.create_product(data)

@router.put("/admin/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    service: CatalogService = Depends(get_catalog_service)
):
    """Обновить продукт (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    updated = await service.update_product(product_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found")
    return updated

@router.delete("/admin/products/{product_id}", status_code=204)
async def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    service: CatalogService = Depends(get_catalog_service)
):
    """Удалить продукт (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    deleted = await service.delete_product(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Product not found")
    

# app/routers/catalog.py — добавьте после эндпоинтов продуктов

# === Админские эндпоинты для категорий ===

@router.post("/admin/categories", response_model=CategoryResponse, status_code=201)
async def create_category(
    data: CategoryCreate,  # 👈 Имя параметра + тип = Swagger автоматически создаст Request body
    current_user: User = Depends(get_current_user),
    service: CatalogService = Depends(get_catalog_service)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return await service.create_category(data)

@router.put("/admin/categories/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    data: CategoryUpdate,  # 👈 То же самое для обновления
    current_user: User = Depends(get_current_user),
    service: CatalogService = Depends(get_catalog_service)
):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    updated = await service.update_category(category_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Category not found")
    return updated

@router.delete("/admin/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    service: CatalogService = Depends(get_catalog_service)
):
    """Деактивировать категорию (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    deleted = await service.delete_category(category_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Category not found")