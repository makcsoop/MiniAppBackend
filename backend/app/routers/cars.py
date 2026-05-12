# app/api/cars.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.dependencies import get_db_session, get_current_user
from app.models.car import CarBrand, CarModel
from app.models.user import User, UserRole
from app.schemas.car import (
    CarBrandCreate, CarBrandUpdate, CarBrandResponse,
    CarModelCreate, CarModelUpdate, CarModelResponse
)

router = APIRouter(prefix="/cars", tags=["cars"])

# =============================================================================
# === ПУБЛИЧНЫЕ ЭНДПОИНТЫ (без авторизации) ===
# =============================================================================

@router.get("/brands", response_model=List[CarBrandResponse])
async def list_brands(db: AsyncSession = Depends(get_db_session)):
    """Получить список всех марок авто"""
    result = await db.execute(select(CarBrand).order_by(CarBrand.name))
    return result.scalars().all()

@router.get("/brands/{brand_id}", response_model=CarBrandResponse)
async def get_brand(brand_id: int, db: AsyncSession = Depends(get_db_session)):
    """Получить марку по ID"""
    brand = await db.get(CarBrand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand

@router.get("/models", response_model=List[CarModelResponse])
async def list_models(
    brand_id: Optional[int] = Query(None, description="Фильтр по марке"),
    db: AsyncSession = Depends(get_db_session)
):
    """Получить список моделей (опционально фильтровать по марке)"""
    query = select(CarModel).order_by(CarModel.name)
    if brand_id:
        query = query.where(CarModel.brand_id == brand_id)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/models/{model_id}", response_model=CarModelResponse)
async def get_model(model_id: int, db: AsyncSession = Depends(get_db_session)):
    """Получить модель по ID"""
    model = await db.get(CarModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

# =============================================================================
# === АДМИНСКИЕ ЭНДПОИНТЫ (только role=ADMIN) ===
# =============================================================================

# --- BRANDS ---

@router.post("/admin/brands", response_model=CarBrandResponse, status_code=201)
async def create_brand(
    data: CarBrandCreate,  # 👈 Swagger автоматически создаст Request body
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Создать марку авто (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    brand = CarBrand(**data.model_dump())
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand

@router.put("/admin/brands/{brand_id}", response_model=CarBrandResponse)
async def update_brand(
    brand_id: int,
    data: CarBrandUpdate,  # 👈 То же самое для обновления
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Обновить марку авто (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    brand = await db.get(CarBrand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(brand, k, v)
    await db.commit()
    await db.refresh(brand)
    return brand

@router.delete("/admin/brands/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Удалить марку авто (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    brand = await db.get(CarBrand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    await db.delete(brand)
    await db.commit()

# --- MODELS ---

@router.post("/admin/models", response_model=CarModelResponse, status_code=201)
async def create_model(
    data: CarModelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Создать модель авто (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Проверка существования марки
    brand = await db.get(CarBrand, data.brand_id)
    if not brand:
        raise HTTPException(status_code=400, detail="Brand not found")
    
    model = CarModel(**data.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model

@router.put("/admin/models/{model_id}", response_model=CarModelResponse)
async def update_model(
    model_id: int,
    data: CarModelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Обновить модель авто (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    model = await db.get(CarModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(model, k, v)
    await db.commit()
    await db.refresh(model)
    return model

@router.delete("/admin/models/{model_id}", status_code=204)
async def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Удалить модель авто (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    model = await db.get(CarModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    await db.delete(model)
    await db.commit()