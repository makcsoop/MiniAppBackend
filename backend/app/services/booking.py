from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
import pytz

from app.models.booking import Booking, BookingStatus
from app.models.product import Product
from app.utils.time_slots import generate_available_slots, check_slot_availability
from app.services.yandex_calendar import YandexCalendarService


class BookingService:
    def __init__(self, db: AsyncSession, calendar_service: Optional[YandexCalendarService] = None):
        self.db = db
        self.calendar = calendar_service

    async def _get_booked_intervals(
        self,
        product_id: Optional[int],
        start: datetime,
        end: datetime,
        exclude_statuses: Optional[List[BookingStatus]] = None
    ) -> List[Tuple[datetime, datetime]]:
        """Внутренний метод: получение занятых интервалов из БД"""
        exclude_statuses = exclude_statuses or [BookingStatus.CANCELLED]
        
        query = select(Booking.start_time, Booking.end_time).where(
            Booking.start_time < end,
            Booking.end_time > start,
            Booking.status.not_in(exclude_statuses)
        )
        if product_id:
            query = query.where(Booking.product_id == product_id)
            
        result = await self.db.execute(query)
        return [tuple(row) for row in result.all()]

    async def get_available_slots(
        self,
        product_id: Optional[int],
        start_date: datetime,
        end_date: datetime,
        slot_duration_minutes: int = 60,
        timezone_str: str = "Europe/Moscow",
        buffer_minutes: int = 15
    ) -> List[datetime]:
        """Получить список доступных слотов (только будущие, naive в Moscow)"""
        tz = pytz.timezone(timezone_str)
        duration = slot_duration_minutes or 60
        
        if product_id:
            product = await self.db.get(Product, product_id)
            if product and getattr(product, 'duration_minutes', None):
                duration = product.duration_minutes
        
        def to_naive(dt: datetime) -> datetime:
            return dt.astimezone(tz).replace(tzinfo=None) if dt.tzinfo else dt
        
        start_naive = to_naive(start_date)
        end_naive = to_naive(end_date)
        now_naive = datetime.now(tz).replace(tzinfo=None)
        
        if start_naive < now_naive:
            start_naive = now_naive
        if start_naive >= end_naive:
            return []
        
        booked = await self._get_booked_intervals(product_id, start_naive, end_naive, [BookingStatus.CANCELLED])
        
        if self.calendar:
            try:
                cal_booked = await asyncio.to_thread(self.calendar.get_busy_intervals, start_naive, end_naive)
                booked.extend([(to_naive(s), to_naive(e)) for s, e in cal_booked])
            except Exception as e:
                print(f"⚠️ Calendar error: {e}")
        
        slots = generate_available_slots(
            start_date=start_naive, end_date=end_naive,
            slot_duration_minutes=duration, booked_slots=booked,
            timezone_str=timezone_str, buffer_minutes=buffer_minutes
        )
        
        # ✅ Фильтр: только будущие слоты (безопасное naive >= naive)
        return [s for s in slots if s >= now_naive]

    async def create_booking(
        self, user_id: int, product_id: Optional[int], start_time: datetime,
        end_time: datetime, timezone: str = "Europe/Moscow", notes: Optional[str] = None,
        client_name: Optional[str] = None, client_phone: Optional[str] = None
    ) -> Booking:
        booked = await self._get_booked_intervals(product_id, start_time, end_time)
        if not check_slot_availability(start_time, end_time, booked):
            raise ValueError("Selected time slot is not available")
        
        booking = Booking(
            user_id=user_id, product_id=product_id, start_time=start_time,
            end_time=end_time, timezone=timezone, notes=notes,
            client_name=client_name, client_phone=client_phone, status=BookingStatus.PENDING
        )
        self.db.add(booking)
        
        if self.calendar:
            try:
                event_id = await asyncio.to_thread(
                    self.calendar.create_event,
                    title=f"Бронь #{booking.id} — {client_name or 'Клиент'}",
                    start=start_time, end=end_time, description=notes or "", location="СинтезКар"
                )
                if event_id:
                    booking.yandex_event_id = event_id
            except Exception as e:
                print(f"⚠️ Calendar error: {e}")
                
        await self.db.commit()
        return booking

    async def confirm_booking(self, booking_id: int) -> Optional[Booking]:
        booking = await self.db.get(Booking, booking_id)
        if not booking or booking.status != BookingStatus.PENDING:
            return None
        booking.status = BookingStatus.CONFIRMED
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def cancel_booking(self, booking_id: int, reason: Optional[str] = None) -> bool:
        booking = await self.db.get(Booking, booking_id)
        if not booking or booking.status == BookingStatus.CANCELLED:
            return False
        booking.status = BookingStatus.CANCELLED
        if reason:
            booking.notes = f"{booking.notes or ''}\n[Отмена: {reason}]"
        await self.db.commit()
        return True

    async def reschedule_booking(self, booking_id: int, new_start: datetime, new_end: datetime) -> Optional[Booking]:
        booking = await self.db.get(Booking, booking_id)
        if not booking or booking.status != BookingStatus.CONFIRMED:
            return None
        booked = await self._get_booked_intervals(
            booking.product_id, new_start, new_end, [BookingStatus.CANCELLED, BookingStatus.PENDING]
        )
        booked = [(s, e) for s, e in booked if not (s == booking.start_time and e == booking.end_time)]
        if not check_slot_availability(new_start, new_end, booked):
            raise ValueError("New time slot is not available")
        booking.start_time, booking.end_time = new_start, new_end
        await self.db.commit()
        await self.db.refresh(booking)
        return booking