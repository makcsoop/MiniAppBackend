# generate_test_init_data.py
import hmac
import hashlib
import time
import json
import urllib.parse
from app.config import settings

def generate_test_init_data(bot_token: str, user_id: int, username: str = "test_user", first_name: str = "Test") -> str:
    """
    Генерирует валидный initData для тестирования, строго по спецификации Telegram:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    # 1. Формируем JSON пользователя ТОЛЬКО с полями, которые реально шлёт Telegram
    user_obj = {
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "language_code": "ru",
        # "is_premium": True,  # опционально, только если пользователь премиум
        # "photo_url": "...",  # опционально
        # "allows_write_to_pm": True,  # опционально
    }
    
    # Важно: json.dumps с separators=(',', ':') и ensure_ascii=False
    user_json = json.dumps(user_obj, separators=(',', ':'), ensure_ascii=False)
    
    # 2. Собираем данные для проверки (сырые значения, НЕ закодированные)
    auth_date = str(int(time.time()))
    query_id = f"test_{user_id}_{int(time.time())}"
    
    # Данные для подписи (ключи будут отсортированы)
    data_dict = {
        "user": user_json,      # ← сырой JSON, без urllib.parse.quote!
        "auth_date": auth_date,
        "query_id": query_id,
    }
    
    # 3. Формируем data_check_string: сортировка по ключам + \n между парами
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_dict.items())
    )
    
    # 4. Вычисляем секретный ключ: HMAC-SHA256("WebAppData", bot_token)
    # 👆 ВАЖНО: "WebAppData", а не "WebApp"!
    secret_key = hmac.new(
        b"WebAppData", 
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
    for k, v in sorted(data_dict.items()):
        # Кодируем значение, но safe='' чтобы кодировать ВСЁ, включая / и :
        init_data_parts.append(f"{k}={urllib.parse.quote(v, safe='')}")
    
    # Добавляем hash в конце (также отсортированный по ключу)
    init_data_parts.append(f"hash={computed_hash}")
    
    return "&".join(init_data_parts)


if __name__ == "__main__":
    # Проверка: токен должен быть в .env или передан явно
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token == "123456789:AAF...":
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env или имеет значение по умолчанию")
        print("💡 Заполните .env реальным токеном от @BotFather")
        exit(1)
    
    # Генерируем initData для тестового пользователя
    result = generate_test_init_data(token, 123456789, "demo_user", "Demo")
    
    print("✅ Сгенерирован initData для тестирования:")
    print("-" * 80)
    print(result)
    print("-" * 80)
    
    # Быстрая самопроверка (опционально)
    try:
        from app.utils.telegram_validator import validate_telegram_init_data
        parsed = validate_telegram_init_data(result, token)
        print(f"✅ Самопроверка прошла!")
        print(f"   User: {parsed.get('user')}")
        print(f"   Telegram ID: {parsed.get('telegram_id')}")
    except ImportError:
        print("⚠️  Модуль валидации не найден, пропущена самопроверка")
    except Exception as e:
        print(f"❌ Самопроверка не прошла: {e}")
        print("\n💡 Убедитесь, что:")
        print("   1. TELEGRAM_BOT_TOKEN в .env совпадает с токеном в скрипте")
        print("   2. Валидатор использует b'WebAppData' как префикс ключа")
        print("   3. data_check_string формируется с сортировкой ключей и \\n между парами")