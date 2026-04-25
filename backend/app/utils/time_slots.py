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
    
    :param start_date: Начало периода поиска
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
    
    # Нормализуем даты
    current = tz.localize(start_date.replace(hour=0, minute=0, second=0, microsecond=0))
    end = tz.localize(end_date.replace(hour=23, minute=59, second=59, microsecond=999999))
    
    slot_delta = timedelta(minutes=slot_duration_minutes)
    buffer_delta = timedelta(minutes=buffer_minutes)
    
    while current < end:
        hour = current.hour + current.minute / 60
        
        # Проверяем рабочие часы
        if working_hours[0] <= hour < working_hours[1]:
            slot_end = current + slot_delta
            
            # Проверяем, что слот не выходит за рамки рабочего дня
            end_hour = slot_end.hour + slot_end.minute / 60
            if end_hour <= working_hours[1]:
                is_available = True
                
                # Проверяем пересечения с занятыми слотами
                for booked_start, booked_end in booked_slots:
                    # Пересечение: не (slot_end <= booked_start or current >= booked_end)
                    if not (slot_end <= booked_start or current >= booked_end):
                        is_available = False
                        break
                
                if is_available:
                    slots.append(current)
        
        current += slot_delta
    
    return slots


def check_slot_availability(
    requested_start: datetime,
    requested_end: datetime,
    booked_slots: List[Tuple[datetime, datetime]],
    buffer_minutes: int = 0
) -> bool:
    """
    Проверяет, свободен ли запрошенный интервал.
    
    :param requested_start: Начало запрошенного слота
    :param requested_end: Конец запрошенного слота
    :param booked_slots: Список занятых интервалов
    :param buffer_minutes: Буфер между слотами в минутах
    :return: True если слот свободен
    """
    if buffer_minutes > 0:
        buffer = timedelta(minutes=buffer_minutes)
        requested_start = requested_start - buffer
        requested_end = requested_end + buffer
    
    for booked_start, booked_end in booked_slots:
        if not (requested_end <= booked_start or requested_start >= booked_end):
            return False
    
    return True


def parse_yandex_datetime(dt_str: str, timezone_str: str = "Europe/Moscow") -> datetime:
    """
    Парсит дату из формата Яндекс.Календаря в datetime с часовым поясом.
    
    Яндекс возвращает даты в формате:
    - "2026-04-24T10:00:00+03:00" (с часовым поясом)
    - "2026-04-24T10:00:00" (без пояса — тогда используем default)
    """
    tz = pytz.timezone(timezone_str)
    
    # Пробуем распарсить с часовым поясом
    if '+' in dt_str or dt_str.endswith('Z'):
        dt_str = dt_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = tz.localize(dt)
        return dt
    else:
        # Без пояса — локализуем вручную
        dt = datetime.fromisoformat(dt_str)
        return tz.localize(dt)