from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user
from app.schemas.user import UserResponse
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/verify", response_model=UserResponse)
async def verify_user(current_user: User = Depends(get_current_user)):
    """
    Проверяет валидность initData и возвращает профиль пользователя.
    Вызывается при старте Mini App.
    """
    return current_user

@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Получение текущего профиля (требует валидного initData в заголовке)."""
    return current_user