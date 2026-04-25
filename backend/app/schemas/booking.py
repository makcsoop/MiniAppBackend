# app/schemas/booking.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Optional, List
from app.models.booking import BookingStatus

class BookingCreate(BaseModel):
    product_id: Optional[int] = None
    start_time: datetime = Field(..., description="Время начала в формате ISO 8601")
    end_time: datetime = Field(..., description="Время окончания в формате ISO 8601")
    timezone: str = Field(default="Europe/Moscow", pattern=r"^[A-Za-z_/]+$")
    notes: Optional[str] = Field(None, max_length=500)
    client_name: Optional[str] = Field(None, max_length=100)
    client_phone: Optional[str] = Field(None, pattern=r"^\+?[0-9\s\-\(\)]{10,20}$")

    @field_validator('end_time')
    @classmethod
    def end_must_be_after_start(cls, end: datetime, values) -> datetime:
        start = values.data.get('start_time') if hasattr(values, 'data') else None
        if start and end <= start:
            raise ValueError('end_time must be after start_time')
        return end

class BookingUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    client_name: Optional[str] = Field(None, max_length=100)
    client_phone: Optional[str] = Field(None, pattern=r"^\+?[0-9\s\-\(\)]{10,20}$")
    status: Optional[BookingStatus] = None

class BookingResponse(BaseModel):
    id: int
    user_id: int
    product_id: Optional[int]
    start_time: datetime
    end_time: datetime
    timezone: str
    status: BookingStatus
    notes: Optional[str]
    client_name: Optional[str]
    client_phone: Optional[str]
    yandex_event_id: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AvailableSlotResponse(BaseModel):
    start: datetime
    end: datetime
    available: bool = True

class SlotsQuery(BaseModel):
    product_id: Optional[int] = None
    start_date: datetime
    end_date: datetime
    slot_duration: int = Field(default=60, ge=15, le=480)  # от 15 мин до 8 часов
    timezone: str = Field(default="Europe/Moscow")