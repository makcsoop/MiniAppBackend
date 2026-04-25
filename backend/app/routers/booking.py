# app/routers/booking.py
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
from app.dependencies import get_db_session, get_current_user
from app.models.user import User, UserRole
from app.models.booking import Booking, BookingStatus
from app.schemas.booking import (
    BookingCreate, BookingUpdate, BookingResponse,
    SlotsQuery, AvailableSlotResponse
)
from app.services.booking import BookingService

router = APIRouter(prefix="/booking", tags=["Booking"])


# ✅ Правильная зависимость: без аннотации возврата сложного типа
def get_booking_service(request: Request, db: AsyncSession = Depends(get_db_session)) -> BookingService:
    """Factory для BookingService — берёт календарь из app.state"""
    calendar = getattr(request.app.state, "yandex_calendar", None)
    return BookingService(db=db, calendar_service=calendar)


@router.get("/slots", response_model=List[AvailableSlotResponse])
async def get_available_slots(
    query: SlotsQuery = Depends(),
    service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user)
):
    """Получить список доступных слотов для бронирования"""
    try:
        slots = await service.get_available_slots(
            product_id=query.product_id,
            start_date=query.start_date,
            end_date=query.end_date,
            slot_duration_minutes=query.slot_duration,
            timezone_str=query.timezone
        )
        
        result = []
        for slot_start in slots:
            from datetime import timedelta
            slot_end = slot_start + timedelta(minutes=query.slot_duration)
            result.append(AvailableSlotResponse(start=slot_start, end=slot_end))
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch slots: {str(e)}")


@router.post("/", response_model=BookingResponse, status_code=201)
async def create_booking(
    data: BookingCreate,
    service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user)
):
    """Создать новое бронирование"""
    try:
        booking = await service.create_booking(
            user_id=current_user.id,
            product_id=data.product_id,
            start_time=data.start_time,
            end_time=data.end_time,
            timezone=data.timezone,
            notes=data.notes,
            client_name=data.client_name,
            client_phone=data.client_phone
        )
        return booking
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create booking: {str(e)}")


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: int,
    service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user)
):
    """Получить информацию о бронировании"""
    booking = await service.db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Проверка прав
    if booking.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return booking


@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: int,
    data: BookingUpdate,
    service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user)
):
    """Обновить бронирование"""
    booking = await service.db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Перенос времени
    if data.start_time or data.end_time:
        if not (data.start_time and data.end_time):
            raise HTTPException(status_code=400, detail="Both start_time and end_time must be provided")
        try:
            booking = await service.reschedule_booking(booking_id, data.start_time, data.end_time)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
    
    # Обновление полей
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(booking, key) and value is not None:
            setattr(booking, key, value)
    
    await service.db.commit()
    await service.db.refresh(booking)
    return booking


@router.put("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(
    booking_id: int,
    service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user)
):
    """Подтвердить бронирование (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    booking = await service.confirm_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found or already confirmed")
    return booking


@router.put("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: int,
    reason: Optional[str] = Query(None, max_length=200),
    service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user)
):
    """Отменить бронирование"""
    booking = await service.db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    if booking.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    
    success = await service.cancel_booking(booking_id, reason)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel booking")
    
    await service.db.refresh(booking)
    return booking


@router.delete("/{booking_id}", status_code=204)
async def delete_booking(
    booking_id: int,
    service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user)
):
    """Удалить бронирование (только админ)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    booking = await service.db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Удаляем из календаря
    if service.calendar and booking.yandex_event_id:
        service.calendar.delete_event(booking.yandex_event_id)
    
    await service.db.delete(booking)
    await service.db.commit()