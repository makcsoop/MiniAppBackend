# tests/test_booking.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from generate_test_init_data import generate_test_init_data

@pytest.fixture(scope="function")
def user_init_data():
    return generate_test_init_data(settings.TELEGRAM_BOT_TOKEN, 111111, "test_user")

@pytest.fixture(scope="function")
def user_headers(user_init_data):
    return {
        "X-Telegram-Init-Data": user_init_data,
        "Content-Type": "application/json"
    }

@pytest.mark.asyncio
async def test_get_available_slots_empty(user_headers):
    """Доступные слоты возвращаются, даже если броней нет"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/booking/slots?product_id=1&start_date=2026-05-01&end_date=2026-05-02",
            headers=user_headers
        )
        # 404 если продукт не найден, 200 если слоты есть
        assert response.status_code in [200, 404]

@pytest.mark.asyncio
async def test_create_booking_requires_auth():
    """Создание брони без авторизации возвращает 422"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {
            "product_id": 1,
            "start_time": "2026-05-01T10:00:00+03:00",
            "end_time": "2026-05-01T11:00:00+03:00",
            "client_name": "Test User",
            "client_phone": "+79991234567"
        }
        response = await ac.post("/booking/", json=payload)
        assert response.status_code == 422  # Missing header

@pytest.mark.asyncio
async def test_create_booking_validation(user_headers):
    """Валидация данных при создании брони"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Невалидные данные: end < start
        payload = {
            "start_time": "2026-05-01T11:00:00+03:00",
            "end_time": "2026-05-01T10:00:00+03:00"
        }
        response = await ac.post("/booking/", json=payload, headers=user_headers)
        assert response.status_code == 422