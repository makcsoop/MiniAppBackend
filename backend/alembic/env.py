# backend/alembic/env.py
import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 👇 1. Добавляем корень проекта в path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 👇 2. Импортируем Base (все модели подтянутся из __init__.py)
from app.models import Base

# 👇 3. КЛЮЧЕВОЕ: связываем Alembic с метаданными
target_metadata = Base.metadata

# Настройка config
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 👇 4. Подставляем DATABASE_URL из .env
from app.config import settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def get_url():
    """Заменяет asyncpg на psycopg2 для синхронных миграций"""
    url = config.get_main_option("sqlalchemy.url")
    if url and "asyncpg" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_url(),
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()