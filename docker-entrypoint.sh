#!/bin/bash
set -e

echo "🔄 Applying database migrations..."

# Ждём, пока БД станет доступна (для первого запуска)
for i in {1..30}; do
    if alembic upgrade head 2>/dev/null; then
        echo "✅ Migrations applied successfully"
        break
    fi
    echo "⏳ Waiting for database... ($i/30)"
    sleep 2
done

echo "🚀 Starting FastAPI server..."
exec "$@"