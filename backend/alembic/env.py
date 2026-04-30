# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# 👇 Добавляем /app в пути импорта (для Docker)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Base  # Теперь импорт сработает

# Настройка логирования Alembic
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 👇 КЛЮЧЕВОЕ: используем синхронный драйвер для миграций
# Заменяем asyncpg на psycopg2 только для Alembic
target_metadata = Base.metadata

def get_url():
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    # Заменяем asyncpg на psycopg2 для синхронных миграций
    if url and "asyncpg" in url:
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url

def run_migrations_offline() -> None:
    """Запуск миграций в оффлайн-режиме (без подключения к БД)"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Запуск миграций в онлайн-режиме (с подключением к БД)"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=get_url(),  # 👇 Используем синхронный URL
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()