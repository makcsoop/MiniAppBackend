# app/utils/telegram_validator.py
import hmac
import hashlib
import urllib.parse
import json
from datetime import datetime
from fastapi import HTTPException, status

def validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Валидирует initData из Telegram Mini App.
    
    Важно: Telegram.WebApp.initData возвращает уже декодированную строку!
    Не нужно применять urllib.parse.unquote!
    """
    try:
        # ❌ УБИРАЕМ это - НЕ нужно декодировать!
        # if "%" in init_data:
        #     init_data = urllib.parse.unquote(init_data)
        
        print(f"🔍 Validating initData (length: {len(init_data)})")
        print(f"🔍 First 200 chars: {init_data[:200]}")
        
        # Парсим query string
        parsed = {}
        for key, value in urllib.parse.parse_qs(init_data, keep_blank_values=True).items():
            parsed[key] = value[0]
        
        print(f"🔍 Parsed keys: {list(parsed.keys())}")
        
        # Извлекаем hash
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            raise ValueError("Missing hash parameter")
        
        print(f"🔍 Hash received: {received_hash[:16]}...")
        
        # Формируем data_check_string в ТОЧНОМ соответствии со спецификацией Telegram
        # Все ключи сортируются лексикографически
        sorted_keys = sorted(parsed.keys())
        data_check_parts = [f"{key}={parsed[key]}" for key in sorted_keys]
        data_check_string = "\n".join(data_check_parts)
        
        print(f"🔍 Data check string (first 200 chars): {data_check_string[:200]}")
        
        # Вычисляем secret_key: HMAC-SHA256("WebAppData", bot_token)
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Вычисляем хэш
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        print(f"🔍 Computed hash: {computed_hash}")
        
        # Сравниваем
        if not hmac.compare_digest(computed_hash, received_hash):
            print(f"❌ Hash mismatch!")
            print(f"   Expected: {computed_hash}")
            print(f"   Received: {received_hash}")
            raise ValueError("Invalid hash signature")
        
        print(f"✅ Hash valid!")
        
        # Проверяем время (не старше 24 часов)
        auth_date = int(parsed.get("auth_date", "0"))
        current_time = int(datetime.now().timestamp())
        
        if auth_date > current_time + 300:  # +5 минут на разницу часовых поясов
            raise ValueError(f"Auth date in future: {auth_date} > {current_time}")
        
        if current_time - auth_date > 24 * 3600:
            raise ValueError(f"InitData expired: {current_time - auth_date} seconds old")
        
        # Парсим user
        user_json = parsed.get("user", "{}")
        parsed["user"] = json.loads(user_json)
        parsed["telegram_id"] = parsed["user"]["id"]
        
        print(f"✅ Validated user: {parsed['telegram_id']}")
        
        return parsed
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid user JSON in initData: {str(e)}"
        )
    except Exception as e:
        print(f"❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram initData"
        )