# app/services/yandex_calendar.py - РАБОЧАЯ ВЕРСИЯ
import requests
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import pytz
from caldav import DAVClient

class YandexCalendarService:
    """Рабочая версия для Яндекс.Календаря через CalDAV"""
    
    def __init__(
        self,
        oauth_token: str = None,
        calendar_id: str = None,
        timezone: str = "Europe/Moscow",
        yandex_login: str = None,
        yandex_app_password: str = None
    ):
        self.calendar_id = calendar_id
        self.timezone = pytz.timezone(timezone)
        
        # 👇 Исправление: убираем дублирование @yandex.ru
        if yandex_login:
            # Если логин уже содержит @yandex.ru — не добавляем ещё раз
            username = yandex_login if '@' in yandex_login else f"{yandex_login}@yandex.ru"
        elif oauth_token and '@' in oauth_token:
            username = oauth_token
        else:
            username = "oauth"  # fallback
        
        password = yandex_app_password or ""
        
        print(f"🔍 CalDAV auth: username={username}, password={'*' * len(password) if password else '(empty)'}")
        
        self.client = DAVClient(
            url="https://caldav.yandex.ru",
            username=username,
            password=password
        )
        
        # 👇 Проверяем подключение сразу
        try:
            self.principal = self.client.principal()
            calendars = self.principal.calendars()
            print(f"✅ CalDAV connected. Found {len(calendars)} calendar(s)")
        except Exception as e:
            print(f"❌ CalDAV connection failed: {e}")
            raise
    
    # app/services/yandex_calendar.py

    def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        description: str = "",
        location: str = ""
    ) -> Optional[str]:
        """Создаёт событие в Яндекс.Календаре через CalDAV"""
        try:
            # Получаем календари
            calendars = self.principal.calendars()
            if not calendars:
                print("❌ Нет доступных календарей")
                return None
            
            # Выбираем календарь по ID или берём первый
            calendar = None
            if self.calendar_id:
                for cal in calendars:
                    if self.calendar_id in str(cal.url) or cal.get_display_name() == self.calendar_id:
                        calendar = cal
                        break
            
            if not calendar:
                calendar = calendars[0]
                print(f"⚠️ Календарь '{self.calendar_id}' не найден, используем: {calendar.get_display_name()}")
            
            # Нормализуем время с часовым поясом
            tz = self.timezone
            start_local = tz.localize(start) if start.tzinfo is None else start
            end_local = tz.localize(end) if end.tzinfo is None else end
            
            # Форматируем даты для iCal (UTC с буквой Z)
            start_ical = start_local.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
            end_ical = end_local.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
            dtstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            
            # 👇 Ключевое: iCal требует \r\n (CRLF), а не \n
            ical_lines = [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//SintezCar//Booking//RU",
                "BEGIN:VEVENT",
                f"UID:booking-{int(start.timestamp())}@sintezcar",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{start_ical}",
                f"DTEND:{end_ical}",
                f"SUMMARY:{title}",
                f"DESCRIPTION:{description.replace(chr(10), '\\n')}",  # Экранируем переносы
                f"LOCATION:{location}",
                "END:VEVENT",
                "END:VCALENDAR"
            ]
            ical_event = "\r\n".join(ical_lines)  # 👇 CRLF, а не просто \n
            
            print(f"📤 Отправляем в календарь: {ical_event[:200]}...")
            
            # Создаём событие
            event = calendar.save_event(ical_event)
            
            
            if event and event.id:
                print(f"✅ Событие создано: {event.id}")
                return event.id
            else:
                print("⚠️ Событие создано, но ID не возвращён")
                return None
                
        except Exception as e:
            # 👇 Подробный лог ошибки
            print(f"❌ Ошибка создания события: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_busy_intervals(self, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
        """Получает занятые интервалы"""
        intervals = []
        try:
            calendars = self.principal.calendars()
            if not calendars:
                return intervals
            
            calendar = calendars[0]
            events = calendar.date_search(
                start=start_date,
                end=end_date,
                expand=True
            )
            
            for event in events:
                # Парсим время из события
                vevent = event.vobject_instance.vevent
                start = vevent.dtstart.value
                end = vevent.dtend.value if hasattr(vevent, 'dtend') else start + timedelta(hours=1)
                intervals.append((start, end))
            
            print(f"📅 Найдено {len(intervals)} событий в календаре")
            
        except Exception as e:
            print(f"❌ Ошибка получения событий: {e}")
        
        return intervals