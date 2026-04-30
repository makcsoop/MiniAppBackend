from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.routers import auth, catalog, booking, payment
from app.services.yandex_calendar import YandexCalendarService

from app.utils.cache import cache



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Инициализация календаря
    yandex_calendar = None
    
    # 👇 Используем логин/пароль для CalDAV
    if settings.YANDEX_LOGIN and settings.YANDEX_APP_PASSWORD:
        try:
            from app.services.yandex_calendar import YandexCalendarService
            yandex_calendar = YandexCalendarService(
                yandex_login=settings.YANDEX_LOGIN,           # 👈 Новый параметр
                yandex_app_password=settings.YANDEX_APP_PASSWORD,  # 👈 Новый параметр
                calendar_id=settings.YANDEX_CALENDAR_ID
            )
            print("✅ Yandex Calendar connected via CalDAV")
        except Exception as e:
            print(f"⚠️ Calendar init failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠️ YANDEX_LOGIN or YANDEX_APP_PASSWORD not set — calendar disabled")
    
    app.state.yandex_calendar = yandex_calendar
    
    await cache.connect()
    print("🚀 Server starting...")
    yield
    await cache.close()
    print("🛑 Server shutting down...")

app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене: ["https://t.me/ваш_бот"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(booking.router)
app.include_router(payment.router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}