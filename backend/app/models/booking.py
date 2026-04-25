# app/models/booking.py
from sqlalchemy import String, Integer, DateTime, Enum, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from app.models import Base

class BookingStatus(str, enum.Enum):
    PENDING = "pending"      # Ожидает подтверждения
    CONFIRMED = "confirmed"  # Подтверждена
    CANCELLED = "cancelled"  # Отменена
    COMPLETED = "completed"  # Услуга оказана

class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Связи
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user: Mapped["User"] = relationship(back_populates="bookings")
    
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    product: Mapped["Product | None"] = relationship(back_populates="bookings")
    
    # Время бронирования
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    
    # Статус и метаданные
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.PENDING)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    
    # Интеграция с Яндекс.Календарём
    yandex_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    yandex_calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Системные поля
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Индексы для быстрой проверки пересечений
    __table_args__ = (
        Index('idx_bookings_time_range', 'start_time', 'end_time'),
        Index('idx_bookings_user_status', 'user_id', 'status'),
    )