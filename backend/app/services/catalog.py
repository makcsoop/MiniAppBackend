# app/services/catalog.py
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple, Dict, Any
from app.models.product import Product, ProductStatus, ProductType
from app.models.category import Category
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.utils.cache import cache


def _filter_for_cache(obj) -> Dict[str, Any]:
    """
    Конвертирует SQLAlchemy-объект в чистый dict для кэширования.
    Рекурсивно обрабатывает вложенные отношения (например, category).
    """
    if obj is None:
        return None
    
    result = {}
    for key, value in obj.__dict__.items():
        # Пропускаем служебные поля SQLAlchemy
        if key.startswith('_') or key in ('metadata', '_sa_instance_state') or callable(value):
            continue
        
        # Рекурсивно обрабатываем вложенные SQLAlchemy-модели
        if hasattr(value, '__table__'):  # Это тоже модель SQLAlchemy
            result[key] = _filter_for_cache(value)
        elif isinstance(value, list) and value and hasattr(value[0], '__table__'):
            result[key] = [_filter_for_cache(item) for item in value]
        else:
            result[key] = value
    
    return result


def _create_product_from_cache(data: Dict[str, Any]) -> Product:
    """
    Создаёт объект Product из отфильтрованного dict кэша.
    Корректно обрабатывает вложенную категорию.
    """
    # Извлекаем и обрабатываем категорию отдельно
    category_data = data.pop('category', None)
    
    # Создаём продукт без категории
    product = Product(**{k: v for k, v in data.items() if k != 'category'})
    
    # Если есть категория — создаём её и привязываем
    if category_data and isinstance(category_data, dict):
        from app.models.category import Category as CategoryModel
        product.category = CategoryModel(**category_data)
    
    return product


class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # === Категории ===
    async def get_categories(self, only_active: bool = True) -> List[Category]:
        cache_key = cache.categories_key()
        
        # Проверяем кэш
        cached = await cache.get(cache_key)
        if cached and isinstance(cached, list):
            return [Category(**c) for c in cached if isinstance(c, dict)]

        # Запрос к БД
        query = select(Category)
        if only_active:
            query = query.where(Category.is_active == True)
        query = query.order_by(Category.sort_order, Category.name)
        
        result = await self.db.execute(query)
        categories = result.scalars().all()
        
        # Кэшируем чистые dict'ы
        await cache.set(
            cache_key, 
            [_filter_for_cache(c) for c in categories], 
            ttl=600
        )
        return categories

    # === Продукты с пагинацией ===
    async def get_products(
        self,
        skip: int = 0,
        limit: int = 20,
        category_slug: Optional[str] = None,
        product_type: Optional[ProductType] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        search: Optional[str] = None,
        only_active: bool = True,
    ) -> Tuple[List[Product], int]:
        
        # Кэш для простых запросов
        if not search and not min_price and not max_price:
            cache_key = cache.products_list_key(category_slug, page=skip//limit + 1)
            cached = await cache.get(cache_key)
            if cached and isinstance(cached, dict) and 'items' in cached:
                items = [_create_product_from_cache(item) for item in cached['items'] if isinstance(item, dict)]
                return items, cached['total']

        # Запрос к БД
        query = select(Product).options(selectinload(Product.category))
        
        # Фильтры
        if only_active:
            query = query.where(Product.status == ProductStatus.ACTIVE)
        if category_slug:
            query = query.join(Category).where(Category.slug == category_slug)
        if product_type:
            query = query.where(Product.product_type == product_type)
        if min_price is not None:
            query = query.where(Product.price >= min_price)
        if max_price is not None:
            query = query.where(Product.price <= max_price)
        if search:
            query = query.where(
                Product.title.ilike(f"%{search}%") | 
                Product.description.ilike(f"%{search}%")
            )
        
        # Пагинация
        count_query = select(func.count(Product.id))
        if only_active:
            count_query = count_query.where(Product.status == ProductStatus.ACTIVE)
        # ... (дублируем фильтры для count_query как у вас было) ...
        
        total = await self.db.scalar(count_query)
        query = query.order_by(Product.is_featured.desc(), Product.sort_order, Product.title)
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        # Кэшируем
        if not search and not min_price and not max_price:
            cache_key = cache.products_list_key(category_slug, page=skip//limit + 1)
            await cache.set(cache_key, {
                'items': [_filter_for_cache(p) for p in products],
                'total': total
            }, ttl=120)
        
        return products, total

    # === Получение одного продукта ===
    async def get_product(self, product_id: int) -> Optional[Product]:
        cache_key = cache.product_key(product_id)
        
        # Проверяем кэш
        cached = await cache.get(cache_key)
        if cached and isinstance(cached, dict):
            return _create_product_from_cache(cached)  # 👇 Используем новую функцию
        
        # Запрос к БД с подгрузкой категории
        query = select(Product).options(
            selectinload(Product.category)
        ).where(Product.id == product_id)
        
        result = await self.db.execute(query)
        product = result.scalars().first()
        
        if product:
            # 👇 Кэшируем через _filter_for_cache (рекурсивно, с категорией)
            await cache.set(cache_key, _filter_for_cache(product), ttl=300)
        return product

    # === CRUD продуктов ===
    async def create_product(self,  ProductCreate) -> Product:
        product = Product(**data.model_dump())
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product, attribute_names=['category'])
        await cache.delete("catalog:products:*")
        await cache.delete(cache.categories_key())
        return product

    async def update_product(self, product_id: int,  ProductUpdate) -> Optional[Product]:
        product = await self.get_product(product_id)
        if not product:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(product, key):
                setattr(product, key, value)
        await self.db.commit()
        await self.db.refresh(product)
        await cache.delete(cache.product_key(product_id))
        await cache.delete("catalog:products:*")
        return product

    async def delete_product(self, product_id: int) -> bool:
        product = await self.get_product(product_id)
        if not product:
            return False
        await self.db.delete(product)
        await self.db.commit()
        await cache.delete(cache.product_key(product_id))
        await cache.delete("catalog:products:*")
        return True
    
    # === CRUD категорий ===
    async def create_category(self,  CategoryCreate) -> Category:
        category = Category(**data.model_dump())
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        try:
            await cache.delete(cache.categories_key())
        except Exception:
            pass
        return category

    async def update_category(self, category_id: int,  CategoryUpdate) -> Optional[Category]:
        category = await self.db.get(Category, category_id)
        if not category:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(category, key):
                setattr(category, key, value)
        await self.db.commit()
        await self.db.refresh(category)
        try:
            await cache.delete(cache.categories_key())
        except Exception:
            pass
        return category

    async def delete_category(self, category_id: int) -> bool:
        category = await self.db.get(Category, category_id)
        if not category:
            return False
        category.is_active = False
        await self.db.commit()
        try:
            await cache.delete(cache.categories_key())
        except Exception:
            pass
        return True