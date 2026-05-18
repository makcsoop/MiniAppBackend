import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings
from generate_test_init_data import generate_test_init_data

@pytest.mark.asyncio(loop_scope="function")
async def test_verify_user_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        init_data = generate_test_init_data(settings.TELEGRAM_BOT_TOKEN, 999999)
        headers = {"X-Telegram-Init-Data": init_data}
        response = await ac.post("/auth/verify", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["telegram_id"] == 999999

@pytest.mark.asyncio(loop_scope="function")
async def test_verify_user_invalid_hash():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {"X-Telegram-Init-Data": "user=%7B%22id%22%3A1%7D&auth_date=123&hash=invalid"}
        response = await ac.post("/auth/verify", headers=headers)
        assert response.status_code == 401