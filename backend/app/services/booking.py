# app/services/booking.py
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import asyncio
from app.models.booking import Booking, BookingStatus
from app.models.product import Product
from app.utils.time_slots import generate_available_slots, check_slot_availability
from app.services.yandex_calendar import YandexCalendarService

class BookingService:
    def __init__(self, db: AsyncSession, calendar_service: Optional[YandexCalendarService] = None):
        self.db = db
        self.calendar = calendar_service


    # app/services/booking.py

    async def get_available_slots(
        self,
        product_id: Optional[int],
        start_date: datetime,
        end_date: datetime,
        slot_duration_minutes: int = 60,
        timezone_str: str = "Europe/Moscow",
        buffer_minutes: int = 15
    ) -> List[datetime]:
        """Получить список доступных слотов для бронирования"""
        import pytz
        
        # 👇 ГАРАНТИРОВАННО определяем duration в начале метода
        duration: int = slot_duration_minutes if slot_duration_minutes else 60
        
        # 1. Если указан product_id — пробуем получить длительность из продукта
        if product_id:
            product = await self.db.get(Product, product_id)
            if product and hasattr(product, 'duration_minutes') and product.duration_minutes:
                duration = product.duration_minutes
        
        # 👇 Конвертация дат: любая входящая дата → наивная в нужном таймзоне
        tz = pytz.timezone(timezone_str)
        
        def to_naive_local(dt: datetime) -> datetime:
            """Приводит datetime к наивному в указанном таймзоне"""
            if dt.tzinfo is not None:
                dt = dt.astimezone(tz).replace(tzinfo=None)
            return dt
        
        start_date = to_naive_local(start_date)
        end_date = to_naive_local(end_date)
        
        # 2. Получаем занятые слоты из БД
        booked = await self._get_booked_intervals(
            product_id=product_id,
            start=start_date,
            end=end_date,
            exclude_statuses=[BookingStatus.CANCELLED]
        )
        
        # 3. Если подключен Яндекс.Календарь — добавляем события
        if self.calendar:
            calendar_booked = await asyncio.to_thread(
                self.calendar.get_busy_intervals,
                start_date,
                end_date
            )
            booked.extend(calendar_booked)
        
        # 4. Генерируем доступные слоты
        return generate_available_slots(
            start_date=start_date,
            end_date=end_date,
            slot_duration_minutes=duration,  # 👈 Теперь точно определена
            booked_slots=booked,
            timezone_str=timezone_str,
            buffer_minutes=buffer_minutes
        )

    async def _get_booked_intervals(
        self,
        product_id: Optional[int],
        start: datetime,
        end: datetime,
        exclude_statuses: Optional[List[BookingStatus]] = None
    ) -> List[Tuple[datetime, datetime]]:
        """Получить список занятых интервалов из БД"""
        exclude_statuses = exclude_statuses or [BookingStatus.CANCELLED]
        
        query = select(Booking.start_time, Booking.end_time).where(
            Booking.start_time < end,
            Booking.end_time > start,
            Booking.status.not_in(exclude_statuses)
        )
        
        if product_id:
            query = query.where(Booking.product_id == product_id)
        
        result = await self.db.execute(query)
        return result.all()

    async def create_booking(
        self,
        user_id: int,
        product_id: Optional[int],
        start_time: datetime,
        end_time: datetime,
        timezone: str = "Europe/Moscow",
        notes: Optional[str] = None,
        client_name: Optional[str] = None,
        client_phone: Optional[str] = None
    ) -> Booking:
        """Создать новое бронирование"""
        # 1. Проверяем доступность слота
        booked = await self._get_booked_intervals(
            product_id=product_id,
            start=start_time,
            end=end_time
        )
        
        if not check_slot_availability(start_time, end_time, booked):
            raise ValueError("Selected time slot is not available")
        
        # 2. Создаём бронь в БД
        booking = Booking(
            user_id=user_id,
            product_id=product_id,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            notes=notes,
            client_name=client_name,
            client_phone=client_phone,
            status=BookingStatus.PENDING
        )
        self.db.add(booking)
        
        # 3. Если подключен календарь — создаём событие (синхронный вызов)
        if self.calendar:
            try:
                event_id = await asyncio.to_thread(
                    self.calendar.create_event,
                    title=f"Бронь #{booking.id} — {client_name or 'Клиент'}",
                    start=start_time,
                    end=end_time,
                    description=notes or "",
                    location="СинтезКар"
                )
                if event_id:
                    booking.yandex_event_id = event_id
            except Exception as e:
                print(f"⚠️ Calendar error (не блокируем бронь): {e}")
        
        # 4. ОДИН коммит в конце
        await self.db.commit()
        return booking

    async def confirm_booking(self, booking_id: int) -> Optional[Booking]:
        """Подтвердить бронирование и создать событие в календаре"""
        booking = await self.db.get(Booking, booking_id)
        if not booking or booking.status != BookingStatus.PENDING:
            return None
        
        booking.status = BookingStatus.CONFIRMED
        
        if self.calendar:
            try:
                event_id = await asyncio.to_thread(
                    self.calendar.create_event,
                    title=f"Бронь #{booking.id} — {booking.client_name or 'Клиент'}",
                    start=booking.start_time,
                    end=booking.end_time,
                    description=booking.notes or "",
                    location="СинтезКар"
                )
                if event_id:
                    booking.yandex_event_id = event_id
            except Exception as e:
                print(f"⚠️ Calendar error при подтверждении: {e}")
        
        await self.db.commit()
        await self.db.refresh(booking)
        return booking

    async def cancel_booking(self, booking_id: int, reason: Optional[str] = None) -> bool:
        """Отменить бронирование"""
        booking = await self.db.get(Booking, booking_id)
        if not booking or booking.status == BookingStatus.CANCELLED:
            return False
        
        booking.status = BookingStatus.CANCELLED
        if reason:
            booking.notes = f"{booking.notes or ''}\n[Отмена: {reason}]"
        
        if self.calendar and booking.yandex_event_id:
            try:
                await asyncio.to_thread(self.calendar.delete_event, booking.yandex_event_id)
            except Exception as e:
                print(f"⚠️ Calendar error при отмене: {e}")
        
        await self.db.commit()
        return True

    async def reschedule_booking(
        self,
        booking_id: int,
        new_start: datetime,
        new_end: datetime
    ) -> Optional[Booking]:
        """Перенести бронирование на другое время"""
        booking = await self.db.get(Booking, booking_id)
        if not booking or booking.status != BookingStatus.CONFIRMED:
            return None
        
        # Проверяем доступность нового слота
        booked = await self._get_booked_intervals(
            product_id=booking.product_id,
            start=new_start,
            end=new_end,
            exclude_statuses=[BookingStatus.CANCELLED, BookingStatus.PENDING]
        )
        # Исключаем текущую бронь из проверки
        booked = [(s, e) for s, e in booked if not (s == booking.start_time and e == booking.end_time)]
        
        if not check_slot_availability(new_start, new_end, booked):
            raise ValueError("New time slot is not available")
        
        booking.start_time = new_start
        booking.end_time = new_end
        
        if self.calendar and booking.yandex_event_id:
            try:
                await asyncio.to_thread(
                    self.calendar.update_event,
                    event_id=booking.yandex_event_id,
                    start=new_start,
                    end=new_end
                )
            except Exception as e:
                print(f"⚠️ Calendar error при переносе: {e}")
        
        await self.db.commit()
        await self.db.refresh(booking)
        return booking