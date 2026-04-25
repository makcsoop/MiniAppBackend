from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple
from app.models.product import Product, ProductStatus, ProductType
from app.models.category import Category
from app.schemas.product import ProductCreate, ProductUpdate
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.utils.cache import cache


class CatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # === Категории ===
    async def get_categories(self, only_active: bool = True) -> List[Category]:
        cache_key = cache.categories_key()
        cached = await cache.get(cache_key)
        if cached:
            return [Category(**c) for c in cached]

        query = select(Category)
        if only_active:
            query = query.where(Category.is_active == True)
        query = query.order_by(Category.sort_order, Category.name)
        
        result = await self.db.execute(query)
        categories = result.scalars().all()
        
        # Кэшируем
        await cache.set(cache_key, [c.__dict__ for c in categories], ttl=600)
        return categories

    # === Продукты с пагинацией и фильтрами ===
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
        # Проверяем кэш для простых запросов
        if not search and not min_price and not max_price:
            cache_key = cache.products_list_key(category_slug, page=skip//limit + 1)
            cached = await cache.get(cache_key)
            if cached and 'items' in cached:
                return cached['items'], cached['total']

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
        
        # Считаем общее количество для пагинации
        count_query = select(func.count(Product.id))
        if only_active:
            count_query = count_query.where(Product.status == ProductStatus.ACTIVE)
        if category_slug:
            count_query = count_query.join(Category).where(Category.slug == category_slug)
        if product_type:
            count_query = count_query.where(Product.product_type == product_type)
        if min_price is not None:
            count_query = count_query.where(Product.price >= min_price)
        if max_price is not None:
            count_query = count_query.where(Product.price <= max_price)
        if search:
            count_query = count_query.where(
                Product.title.ilike(f"%{search}%") | 
                Product.description.ilike(f"%{search}%")
            )

        total = await self.db.scalar(count_query)
        
        # Применяем пагинацию и сортировку
        query = query.order_by(Product.is_featured.desc(), Product.sort_order, Product.title)
        query = query.offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        # Кэшируем результат (только если нет сложного поиска)
        if not search and not min_price and not max_price:
            await cache.set(cache_key, {
                'items': [p.__dict__ for p in products],
                'total': total
            }, ttl=120)
        
        return products, total

    # === CRUD для продуктов ===
    async def get_product(self, product_id: int) -> Optional[Product]:
        # Проверяем кэш
        cache_key = cache.product_key(product_id)
        cached = await cache.get(cache_key)
        if cached:
            return Product(**cached)
        
        query = select(Product).options(
        selectinload(Product.category)
    ).where(Product.id == product_id)
        result = await self.db.execute(query)
        product = result.scalars().first()
        
        if product:
            await cache.set(cache_key, product.__dict__, ttl=300)
        return product

    async def create_product(self, data: ProductCreate) -> Product:
        product = Product(**data.model_dump())
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product, attribute_names=['category'])                
        # Инвалидируем кэш списка
        await cache.delete("catalog:products:*")
        await cache.delete(cache.categories_key())
        return product

    async def update_product(self, product_id: int, data: ProductUpdate) -> Optional[Product]:
        product = await self.get_product(product_id)
        if not product:
            return None
        
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        
        await self.db.commit()
        await self.db.refresh(product)
        
        # Инвалидируем кэш
        await cache.delete(cache.product_key(product_id))
        await cache.delete("catalog:products:*")
        return product

    async def delete_product(self, product_id: int) -> bool:
        product = await self.get_product(product_id)
        if not product:
            return False
        
        await self.db.delete(product)
        await self.db.commit()
        
        # Инвалидируем кэш
        await cache.delete(cache.product_key(product_id))
        await cache.delete("catalog:products:*")
        return True
    
    # app/services/catalog.py — добавьте в класс CatalogService

    async def create_category(self, data: CategoryCreate) -> Category:  # ← data: перед типом!
        category = Category(**data.model_dump())  # ← теперь data доступен
        self.db.add(category)
        await self.db.commit()
        await self.db.refresh(category)
        
        try:
            await cache.delete(cache.categories_key())
        except Exception:
            pass
        return category

    async def update_category(self, category_id: int, data: CategoryUpdate) -> Optional[Category]:
        update_data = data.model_dump(exclude_unset=True)  # ← теперь работает
        category = await self.db.get(Category, category_id)
        if not category:
            return None
        for key, value in update_data.items():
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
        
        category.is_active = False  # Мягкое удаление
        await self.db.commit()
        try:
            await cache.delete(cache.categories_key())
        except Exception:
            pass
        return True