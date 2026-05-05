# tests/test_catalog.py — минимальные тесты без БД
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
async def test_list_categories_empty():
    """Категории возвращаются даже если база пустая"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/catalog/categories")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_create_product_requires_auth():
    """Создание продукта без заголовка возвращает 422"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"title": "Test", "slug": "test", "price": 100, "product_type": "service"}
        response = await ac.post("/catalog/admin/products", json=payload)
        assert response.status_code == 422  # Missing header

@pytest.mark.asyncio
async def test_create_product_requires_admin(user_headers):
    """Обычный пользователь не может создать продукт"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"title": "Test", "slug": "test", "price": 100, "product_type": "service"}
        response = await ac.post("/catalog/admin/products", json=payload, headers=user_headers)
        # 403 если не админ, 401 если подпись невалидна
        assert response.status_code in [401, 403]