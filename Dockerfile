FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Рабочая директория внутри контейнера
WORKDIR /code

# Системные зависимости для asyncpg и psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Кэшируем установку зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# 👇 КЛЮЧЕВОЕ: добавляем папку backend в пути импорта Python
ENV PYTHONPATH=/code/backend

# Непривилегированный пользователь (безопасность)
RUN useradd -m appuser && chown -R appuser:appuser /code
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Запуск
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]