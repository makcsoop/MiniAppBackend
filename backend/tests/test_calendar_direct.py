# test_calendar_direct.py
from datetime import datetime, timedelta
from app.services.yandex_calendar import YandexCalendarService
from app.config import settings

# Инициализация
calendar = YandexCalendarService(
    oauth_token=settings.YANDEX_OAUTH_TOKEN,
    calendar_id=settings.YANDEX_CALENDAR_ID
)

# Тестовое событие
start = datetime.now() + timedelta(minutes=5)
end = start + timedelta(hours=1)

print(f"🧪 Creating test event: {start} - {end}")
event_id = calendar.create_event(
    title="🧪 Тест из скрипта",
    start=start,
    end=end,
    description="Проверка CalDAV",
    location="СинтезКар"
)
print(f"Result: {event_id}")