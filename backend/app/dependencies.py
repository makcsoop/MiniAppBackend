# app/dependencies.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import defer
from app.database import get_db
from app.models.user import User, UserRole
from app.utils.telegram_validator import validate_telegram_init_data
from app.services.catalog import CatalogService
from app.services.booking import BookingService
from app.config import settings

def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db

async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    # Валидируем initData
    validated = validate_telegram_init_data(x_telegram_init_data, settings.TELEGRAM_BOT_TOKEN)
    
    # Извлекаем данные
    user_info = validated.get("user", {})
    telegram_id = user_info.get("id")
    
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user.id in initData"
        )
    
    # Ищем пользователя
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    # Создаем или обновляем
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=user_info.get("username"),
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            language_code=user_info.get("language_code"),
            is_premium=user_info.get("is_premium", False),
            role=UserRole.USER
        )
        db.add(user)
    else:
        # ✅ ИСПРАВЛЕНО: Обновляем через setattr или update
        user.username = user_info.get("username") or user.username
        user.first_name = user_info.get("first_name") or user.first_name
        user.last_name = user_info.get("last_name") or user.last_name
        user.language_code = user_info.get("language_code") or user.language_code
        user.is_premium = user_info.get("is_premium", user.is_premium)
        user.last_seen = func.now()
    
    await db.commit()
    await db.refresh(user)
    return user

def get_catalog_service(db: AsyncSession = Depends(get_db_session)) -> CatalogService:
    return CatalogService(db)

def get_booking_service(
    db: AsyncSession = Depends(get_db_session),
    request: Request = None
) -> BookingService:
    calendar = None
    if request and hasattr(request.app, 'state'):
        calendar = getattr(request.app.state, 'yandex_calendar', None)
    return BookingService(db=db, calendar_service=calendar)