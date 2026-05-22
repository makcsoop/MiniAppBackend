# app/utils/time_slots.py
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import pytz

def generate_available_slots(
    start_date: datetime,
    end_date: datetime,
    slot_duration_minutes: int,
    working_hours: Tuple[int, int] = (9, 20),  # 9:00 - 20:00
    booked_slots: Optional[List[Tuple[datetime, datetime]]] = None,
    timezone_str: str = "Europe/Moscow",
    buffer_minutes: int = 0
) -> List[datetime]:
    """
    Генерирует список доступных слотов для бронирования.
    
    :param start_date: Начало периода поиска (с учётом времени, наивный или с таймзоной)
    :param end_date: Конец периода поиска
    :param slot_duration_minutes: Длительность одного слота в минутах
    :param working_hours: Кортеж (начало_рабочего_дня, конец_рабочего_дня) в часах
    :param booked_slots: Список занятых интервалов [(start, end), ...]
    :param timezone_str: Часовой пояс
    :param buffer_minutes: Буфер между слотами в минутах
    :return: Список доступных стартовых времён слотов
    """
    tz = pytz.timezone(timezone_str)
    slots = []
    booked_slots = booked_slots or []
    
    # Приводим всё к таймзоне
    def to_tz(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return tz.localize(dt)
        return dt.astimezone(tz)
    
    current = to_tz(start_date)
    end = to_tz(end_date)
    
    slot_delta = timedelta(minutes=slot_duration_minutes)
    work_start_hour, work_end_hour = working_hours
    
    # Корректируем начальное время
    day_start = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
    if current < day_start:
        current = day_start
    
    while current < end:
        # Если вышли за конец рабочего дня – переходим на следующий день
        if current.hour >= work_end_hour or (current.hour == work_end_hour and current.minute > 0):
            current = (current + timedelta(days=1)).replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
            continue
        
        slot_end = current + slot_delta
        
        # Проверяем, что слот не выходит за границы рабочего дня
        if slot_end.hour > work_end_hour or (slot_end.hour == work_end_hour and slot_end.minute > 0):
            current = (current + timedelta(days=1)).replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
            continue
        
        # Проверка занятости
        is_available = True
        for booked_start, booked_end in booked_slots:
            # Приводим занятые слоты к той же таймзоне
            b_start = to_tz(booked_start)
            b_end = to_tz(booked_end)
            if not (slot_end <= b_start or current >= b_end):
                is_available = False
                break
        
        if is_available:
            slots.append(current.replace(tzinfo=None))
        
        current += slot_delta
    
    return slots

def check_slot_availability(
    requested_start: datetime,
    requested_end: datetime,
    booked_slots: List[Tuple[datetime, datetime]],
    buffer_minutes: int = 0
) -> bool:
    """Проверяет, свободен ли запрошенный интервал."""
    if buffer_minutes > 0:
        buffer = timedelta(minutes=buffer_minutes)
        requested_start = requested_start - buffer
        requested_end = requested_end + buffer
    
    for booked_start, booked_end in booked_slots:
        if not (requested_end <= booked_start or requested_start >= booked_end):
            return False
    return True

def parse_yandex_datetime(dt_str: str, timezone_str: str = "Europe/Moscow") -> datetime:
    """Парсит дату из формата Яндекс.Календаря в datetime с часовым поясом."""
    tz = pytz.timezone(timezone_str)
    if '+' in dt_str or dt_str.endswith('Z'):
        dt_str = dt_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt
    else:
        dt = datetime.fromisoformat(dt_str)
        return tz.localize(dt)