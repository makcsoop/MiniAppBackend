# generate_test_init_data.py — ПОЛНОСТЬЮ АВТОНОМНАЯ ВЕРСИЯ
#!/usr/bin/env python3
"""
Генератор initData для тестирования по Telegram ID.
Не требует импортов из проекта — работает автономно.
Использование: python generate_test_init_data.py <telegram_id> [username]
"""

import sys
import os
import hmac
import hashlib
import time
import json
import urllib.parse
from pathlib import Path


def load_env_token(env_path: str = ".env") -> str:
    """Читает TELEGRAM_BOT_TOKEN из .env файла без сторонних библиотек"""
    env_file = Path(env_path)
    if not env_file.exists():
        return ""
    
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() == "TELEGRAM_BOT_TOKEN":
                    return value.strip().strip('"').strip("'")
    return ""


def generate_init_data_by_id(
    bot_token: str,
    telegram_id: int,
    username: str = None,
    first_name: str = None
) -> str:
    """Генерирует валидный initData строго по спецификации Telegram"""
    
    # 1. Формируем user JSON
    user_obj = {
        "id": telegram_id,
        "first_name": first_name or f"User{telegram_id}",
    }
    
    if username:
        user_obj["username"] = username
    else:
        user_obj["username"] = f"user_{telegram_id}"
    
    user_obj["language_code"] = "ru"
    user_obj["allows_write_to_pm"] = True
    
    user_json = json.dumps(user_obj, separators=(',', ':'), ensure_ascii=False)
    
    # 2. Параметры для подписи
    auth_date = str(int(time.time()))
    query_id = f"test_{telegram_id}_{auth_date}"
    
    params = {
        "user": user_json,
        "auth_date": auth_date,
        "query_id": query_id,
    }
    
    # 3. data_check_string
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    
    # 4. Секретный ключ: HMAC-SHA256("WebAppData", bot_token)
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    # 5. Хеш
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # 6. Финальная строка
    init_data_parts = []
    for key, value in sorted(params.items()):
        init_data_parts.append(f"{key}={urllib.parse.quote(value, safe='')}")
    
    init_data_parts.append(f"hash={computed_hash}")
    
    return "&".join(init_data_parts)


def main():
    if len(sys.argv) < 2:
        print("❌ Использование: python generate_test_init_data.py <telegram_id> [username]")
        print("Пример: python generate_test_init_data.py 123456789 my_username")
        sys.exit(1)
    
    telegram_id = int(sys.argv[1])
    username = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Читаем токен из .env без импортов
    bot_token = load_env_token()
    
    if not bot_token or "123456789:AAF" in bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env или имеет значение по умолчанию")
        print("💡 Заполните .env реальным токеном от @BotFather")
        sys.exit(1)
    
    init_data = generate_init_data_by_id(bot_token, telegram_id, username)
    
    print(f"\n✅ initData для Telegram ID {telegram_id}:")
    print("=" * 80)
    print(init_data)
    print("=" * 80)
    
    print(f"\n📋 Пример curl-запроса:")
    print(f"curl -X POST http://localhost:8000/auth/verify \\")
    print(f"  -H 'X-Telegram-Init-Data: \"{init_data}\"' \\")
    print(f"  -H 'Content-Type: application/json' \\")
    print(f"  -d '{{}}'")


if __name__ == "__main__":
    main()