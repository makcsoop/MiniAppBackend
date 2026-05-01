FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# === ШАГ 1: Системные зависимости ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# === ШАГ 2: Python-зависимости (КЭШИРУЕТСЯ!) ===
# 👇 Копируем ТОЛЬКО requirements.txt
COPY requirements.txt .

# 👇 Устанавливаем пакеты
# Этот слой будет пересобираться ТОЛЬКО если изменится requirements.txt
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# === ШАГ 3: Исходный код (меняется часто) ===
# 👇 Копируем код ПОСЛЕ установки зависимостей
# Если вы поменяете код в app/ или bot/, слой с pip install НЕ пересоберётся!
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/seed.py ./seed.py
COPY backend/app ./app
COPY backend/bot ./bot
COPY backend/tests ./tests

# === ШАГ 4: Скрипт запуска ===
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]