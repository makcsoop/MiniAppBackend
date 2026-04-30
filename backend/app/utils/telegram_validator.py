# app/utils/telegram_auth.py
import hmac
import hashlib
import urllib.parse
import json
from datetime import datetime
from fastapi import HTTPException, status

def validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Валидирует initData из Telegram Mini App.
    """
    try:
        # 1. Декодируем URL-encoded строку (если нужно)
        if "%" in init_data:
            init_data = urllib.parse.unquote(init_data)
        
        # 2. Парсим query string в словарь
        # parse_qs возвращает списки значений, берём первый элемент
        parsed = {k: v[0] for k, v in urllib.parse.parse_qs(init_data).items()}
        
        # 3. Извлекаем и удаляем hash из параметров для проверки
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            raise ValueError("Missing hash parameter")
        
        # 👇 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: удаляем также 'signature', если он есть
        # (это не стандартный параметр Telegram, но может приходить от фронтенда)
        parsed.pop("signature", None)
        
        # 4. Формируем data_check_string:
        # - сортируем ключи лексикографически
        # - соединяем пары key=value через \n (перевод строки)
        # - значения уже декодированы на шаге 2
        data_check_string = "\n".join(
            f"{key}={value}" for key, value in sorted(parsed.items())
        )
        
        # 5. Вычисляем секретный ключ: HMAC-SHA256(bot_token, "WebAppData")
        # 👆 ВАЖНО: префикс "WebAppData", а не "WebApp"!
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        # 6. Вычисляем HMAC-SHA256 от data_check_string
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),  # 👆 Обязательно .encode('utf-8')
            hashlib.sha256
        ).hexdigest()
        
        # 7. Сравниваем хеши (защита от timing attack)
        if not hmac.compare_digest(computed_hash, received_hash):
            #Для отладки: раскомментируйте, чтобы увидеть, что не так
            print(f"DEBUG: Expected: {computed_hash}")
            print(f"DEBUG: Received: {received_hash}")
            print(f"DEBUG: Check string: {repr(data_check_string)}")
            raise ValueError("Invalid hash signature")
        
        # 8. Проверяем время (не старше 24 часов)
        auth_date = int(parsed.get("auth_date", "0"))
        if datetime.now().timestamp() - auth_date > 24 * 3600:
            raise ValueError("InitData expired")
        
        # 9. Парсим user из JSON-строки
        user_json = parsed.get("user", "{}")
        parsed["user"] = json.loads(user_json)
        parsed["telegram_id"] = parsed["user"]["id"]  # Удобное поле для поиска в БД
        
        return parsed
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid user JSON in initData: {str(e)}"
        )
    except Exception as e:
        # В продакшене не выводите детали ошибки пользователю
        print(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram initData"
        )