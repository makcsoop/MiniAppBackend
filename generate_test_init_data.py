import hmac
import hashlib
import time
import json
import urllib.parse
from app.config import settings

def generate_test_init_data(bot_token: str, user_id: int, username: str = "test_user") -> str:
    """
    Генерирует валидный initData для тестирования, строго по спецификации Telegram:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    # 1. Формируем JSON пользователя
    user_obj = {
        "id": user_id,
        "username": username,
        "first_name": "Test",
        "language_code": "ru",
        "is_premium": False,
        "role": "admin"
    }
    user_json = json.dumps(user_obj, separators=(',', ':'), ensure_ascii=False)
    
    # 2. Собираем данные для проверки (сырые значения, НЕ закодированные)
    auth_date = str(int(time.time()))
    query_id = "test_query_123"
    
    # Важно: порядок ключей не важен, т.к. потом сортируем, но значения должны быть строками
    data_dict = {
        "user": user_json,      # ← сырой JSON, без urllib.parse.quote!
        "auth_date": auth_date,
        "query_id": query_id
    }
    
    # 3. Формируем data_check_string: сортировка по ключам + перевод строки между парами
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_dict.items())
    )
    
    # 4. Вычисляем секретный ключ: HMAC-SHA256("WebApp", bot_token)
    secret_key = hmac.new(
        b"WebApp", 
        bot_token.encode('utf-8'), 
        hashlib.sha256
    ).digest()
    
    # 5. Вычисляем хеш данных
    computed_hash = hmac.new(
        secret_key, 
        data_check_string.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()
    
    # 6. Формируем финальную строку initData (теперь кодируем значения!)
    init_data_parts = []
    for k, v in data_dict.items():
        init_data_parts.append(f"{k}={urllib.parse.quote(v, safe='')}")
    init_data_parts.append(f"hash={computed_hash}")
    
    return "&".join(init_data_parts)


if __name__ == "__main__":
    # Проверка: токен должен быть в .env или передан явно
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env")
        exit(1)
    
    result = generate_test_init_data(token, 123456789, "demo_user")
    print("✅ Сгенерирован initData:")
    print(result)
    
    # Быстрая самопроверка (опционально)
    from app.utils.telegram_validator import validate_telegram_init_data
    try:
        parsed = validate_telegram_init_data(result)
        print(f"✅ Самопроверка прошла: {parsed}")
    except Exception as e:
        print(f"❌ Самопроверка не прошла: {e}")