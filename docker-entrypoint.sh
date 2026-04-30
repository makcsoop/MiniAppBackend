#!/bin/bash
set -e

echo "🔄 Применяю миграции базы данных..."
alembic upgrade head

echo "🌱 Заполняем БД начальными данными..."
python seed.py  # Запускается внутри контейнера /app/

echo "🚀 Запускаю FastAPI сервер..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 &
API_PID=$!

echo "🤖 Запускаю Telegram Admin Bot..."
python -m bot.admin_bot &
BOT_PID=$!

trap 'echo "⏳ Остановка процессов..."; kill -TERM $API_PID $BOT_PID 2>/dev/null; wait' TERM INT
wait $API_PID $BOT_PID
exit $?