# Dockerfile
FROM python:3.12-slim

# Переменные среды
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Рабочая директория — здесь лежит папка `app/`
WORKDIR /app

# Системные зависимости для asyncpg, psycopg2, caldav
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости (кэширование слоя)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Копируем весь код проекта
# Структура должна быть: /app/app/main.py, /app/alembic/, и т.д.
COPY . .

# Создаём непривилегированного пользователя для безопасности
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Порт для FastAPI
EXPOSE 8000

# Healthcheck для оркестраторов
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entry point: сначала миграции, потом сервер
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]