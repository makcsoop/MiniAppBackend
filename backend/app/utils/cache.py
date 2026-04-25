import json
import redis.asyncio as redis
from typing import Optional, Any
from app.config import settings

class CacheManager:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self.default_ttl = 300  # 5 минут

    async def connect(self):
        self.redis = await redis.from_url(settings.REDIS_URL, decode_responses=True)

    async def close(self):
        if self.redis:
            await self.redis.close()

    async def get(self, key: str) -> Optional[Any]:
        if not self.redis:
            return None
        data = await self.redis.get(key)
        return json.loads(data) if data else None

    async def set(self, key: str, value: Any, ttl: int = None):
        if not self.redis:
            return
        ttl = ttl or self.default_ttl
        await self.redis.setex(key, ttl, json.dumps(value, default=str))

    async def delete(self, pattern: str):
        if not self.redis:
            return
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

    # Специфичные методы для каталога
    def product_key(self, product_id: int) -> str:
        return f"catalog:product:{product_id}"
    
    def products_list_key(self, category_slug: str = None, page: int = 1) -> str:
        base = "catalog:products"
        if category_slug:
            base += f":category:{category_slug}"
        return f"{base}:page:{page}"
    
    def categories_key(self) -> str:
        return "catalog:categories"

# Глобальный инстанс
cache = CacheManager()