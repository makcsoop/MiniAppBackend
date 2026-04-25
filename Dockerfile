# Базовый образ Python (3.12-slim стабилен и лёгкий)
FROM python:3.12-slim

# Отключаем буферизацию вывода для корректных логов
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Системные зависимости для сборки asyncpg, psycopg2 и т.д.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements для кэширования слоёв
COPY requirements.txt .

# Устанавливаем Python-пакеты
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код проекта
COPY . .

# Создаём непривилегированного пользователя (безопасность)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Открываем порт
EXPOSE 8000

# Проверка работоспособности
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Запуск: сначала миграции, потом сервер
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]