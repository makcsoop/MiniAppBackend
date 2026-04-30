from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, UserRole
from app.utils.telegram_validator import validate_telegram_init_data
from app.services.catalog import CatalogService
from app.services.booking import BookingService
from app.config import settings

# 1. Зависимость для сессии БД (обёртка над get_db)
def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db

# 2. Зависимость для получения текущего пользователя (валидация Telegram + upsert)
async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    validated = validate_telegram_init_data(x_telegram_init_data, settings.TELEGRAM_BOT_TOKEN)
    
    # 2. Извлекаем telegram_id и данные пользователя
    user_info = validated.get("user", {})
    telegram_id = user_info.get("id")
    
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing user.id in initData"
        )
    
    # 3. Ищем пользователя по telegram_id (уникальный индекс)
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    # 4. Upsert: создать или обновить
    if not user:
        # Создаём нового пользователя
        user = User(
            telegram_id=telegram_id,
            username=user_info.get("username"),
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            language_code=user_info.get("language_code"),
            is_premium=user_info.get("is_premium", False),
            role=UserRole.USER  # По умолчанию — обычный пользователь
        )
        db.add(user)
    else:
        # Обновляем меняющиеся поля
        update_data = {
            "username": user_info.get("username"),
            "first_name": user_info.get("first_name"),
            "last_name": user_info.get("last_name"),
            "language_code": user_info.get("language_code"),
            "is_premium": user_info.get("is_premium", False),
            "last_seen": func.now()  # Обновляем время последнего визита
        }
        # Обновляем только непустые значения
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        await db.execute(
            update(User).where(User.id == user.id).values(**update_data)
        )
    
    await db.commit()
    await db.refresh(user)
    return user

# 3. Зависимость для сервиса каталога
def get_catalog_service(db: AsyncSession = Depends(get_db_session)) -> CatalogService:
    return CatalogService(db)

def get_booking_service(
    db: AsyncSession = Depends(get_db_session),
    request: Request = None  # Для доступа к app.state
) -> BookingService:
    calendar = request.app.state.yandex_calendar if request else None
    return BookingService(db=db, calendar_service=calendar)