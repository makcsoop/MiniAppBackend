import hmac
import hashlib
from urllib.parse import parse_qs, unquote
from fastapi import HTTPException
from app.config import settings

def validate_telegram_init_data(init_data: str) -> dict:
    """
    Проверяет криптографическую подпись initData от Telegram WebApp.
    Возвращает распарсенные данные пользователя или бросает 401.
    """
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")

    parsed = parse_qs(init_data)
    received_hash = parsed.get("hash", [None])[0]
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash in initData")

    # Удаляем hash из данных для проверки
    data_to_check = {k: v[0] for k, v in parsed.items() if k != "hash"}
    
    # Сортируем ключи и соединяем переводом строки
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_to_check.items())
    )

    # Формируем секретный ключ: HMAC-SHA256(bot_token, "WebApp")
    secret_key = hmac.new(
        b"WebApp", settings.TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256
    ).digest()

    # Считаем хеш данных
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if computed_hash != received_hash:
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    # Проверяем срок жизни (не старше 24 часов)
    auth_date = int(data_to_check.get("auth_date", 0))
    import time
    if time.time() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="InitData expired")

    # Парсим user JSON
    import json
    user_data = json.loads(unquote(data_to_check.get("user", "{}")))
    return {
        "telegram_id": user_data.get("id"),
        "username": user_data.get("username"),
        "first_name": user_data.get("first_name"),
        "last_name": user_data.get("last_name"),
        "language_code": user_data.get("language_code"),
        "is_premium": user_data.get("is_premium", False),
        "role": user_data.get("role"),
    }