# app/services/yandex_calendar.py
import requests
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import pytz
from caldav import DAVClient


class YandexCalendarService:
    """Сервис для работы с Яндекс.Календарём через CalDAV"""
    
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
        
        # Формируем username для CalDAV
        if yandex_login:
            username = yandex_login if '@' in yandex_login else f"{yandex_login}@yandex.ru"
        elif oauth_token and '@' in oauth_token:
            username = oauth_token
        else:
            username = "oauth"
        
        password = yandex_app_password or ""
        
        print(f"🔍 CalDAV auth: username={username}, password={'*' * len(password) if password else '(empty)'}")
        
        self.client = DAVClient(
            url="https://caldav.yandex.ru",
            username=username,
            password=password
        )
        
        # Проверка подключения
        try:
            self.principal = self.client.principal()
            calendars = self.principal.calendars()
            print(f"✅ CalDAV connected. Found {len(calendars)} calendar(s)")
        except Exception as e:
            print(f"❌ CalDAV connection failed: {e}")
            raise
    
    # app/services/yandex_calendar.py

    def _to_utc(self, dt: datetime) -> datetime:
        """Конвертирует datetime в UTC для iCal"""
        if dt.tzinfo is None:
            # Если нет часового пояса — считаем, что это время в настроенном таймзоне
            dt = self.timezone.localize(dt)
        return dt.astimezone(pytz.utc)

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
            calendars = self.principal.calendars()
            if not calendars:
                print("❌ Нет доступных календарей")
                return None
            
            calendar = calendars[0]
            if self.calendar_id:
                for cal in calendars:
                    if self.calendar_id in str(cal.url) or cal.get_display_name() == self.calendar_id:
                        calendar = cal
                        break
            
            # 👇 ИСПРАВЛЕНО: безопасная конвертация в UTC
            start_utc = self._to_utc(start)
            end_utc = self._to_utc(end)
            
            start_ical = start_utc.strftime('%Y%m%dT%H%M%SZ')
            end_ical = end_utc.strftime('%Y%m%dT%H%M%SZ')
            dtstamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            
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
                f"DESCRIPTION:{description.replace(chr(10), '\\n')}",
                f"LOCATION:{location}",
                "END:VEVENT",
                "END:VCALENDAR"
            ]
            ical_event = "\r\n".join(ical_lines)
            
            print(f"📤 Отправляем в календарь: {ical_event[:200]}...")
            
            event = calendar.save_event(ical_event)
            
            if event and event.id:
                print(f"✅ Событие создано: {event.id}")
                return event.id
            return None
                
        except Exception as e:
            print(f"❌ Ошибка создания события: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    # app/services/yandex_calendar.py

    def get_busy_intervals(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Tuple[datetime, datetime]]:
        """Получает занятые интервалы из календаря"""
        intervals = []
        try:
            calendars = self.principal.calendars()
            if not calendars:
                return intervals
            
            calendar = calendars[0]
            
            if start_date.tzinfo is None:
                start_local = self.timezone.localize(start_date)
            else:
                # Если вдруг дата уже с таймзоной — просто конвертируем
                start_local = start_date.astimezone(self.timezone)

            if end_date.tzinfo is None:
                end_local = self.timezone.localize(end_date)
            else:
                end_local = end_date.astimezone(self.timezone)
            
            events = calendar.date_search(
                start=start_local,
                end=end_local,
                expand=True
            )
            
            for event in events:
                vevent = event.vobject_instance.vevent
                start = vevent.dtstart.value
                end = vevent.dtend.value if hasattr(vevent, 'dtend') else start + timedelta(hours=1)
                
                # Возвращаем интервалы в том же формате, что получили
                intervals.append((start, end))
            
            print(f"📅 Найдено {len(intervals)} событий в календаре")
            
        except Exception as e:
            print(f"❌ Ошибка получения событий: {e}")
        
        return intervals
    
    def delete_event(self, event_id: str) -> bool:
        """Удаляет событие по ID"""
        try:
            calendars = self.principal.calendars()
            if not calendars:
                return False
            calendar = calendars[0]
            event = calendar.event_by_uid(event_id)
            if event:
                event.delete()
                print(f"🗑 Событие {event_id} удалено")
                return True
        except Exception as e:
            print(f"❌ Ошибка удаления события: {e}")
        return False
    
    def update_event(
        self,
        event_id: str,
        start: datetime,
        end: datetime,
        title: str = None,
        description: str = None,
        location: str = None
    ) -> bool:
        """Обновляет существующее событие"""
        try:
            # Удаляем старое и создаём новое (проще, чем редактировать iCal)
            self.delete_event(event_id)
            return self.create_event(
                title=title or "Обновлённая бронь",
                start=start,
                end=end,
                description=description or "",
                location=location or ""
            ) is not None
        except Exception as e:
            print(f"❌ Ошибка обновления события: {e}")
            return False