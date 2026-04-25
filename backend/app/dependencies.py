from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, UserRole
from app.utils.telegram_validator import validate_telegram_init_data
from app.services.catalog import CatalogService

# 1. Зависимость для сессии БД (обёртка над get_db)
def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db

# 2. Зависимость для получения текущего пользователя (валидация Telegram + upsert)
async def get_current_user(
    x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    user_data = validate_telegram_init_data(x_telegram_init_data)
    
    stmt = select(User).where(User.telegram_id == user_data["telegram_id"])
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        user = User(**user_data)
        db.add(user)
    else:
        # Обновляем данные, если они изменились
        for key, value in user_data.items():
            if hasattr(user, key):
                setattr(user, key, value)
                
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