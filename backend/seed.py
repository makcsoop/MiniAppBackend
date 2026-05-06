# backend/app/seed.py
import asyncio
import json
from pathlib import Path
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.product import Product, ProductType, ProductStatus


def clean_json_data(data):
    """Рекурсивно убирает пробелы из ключей и строковых значений JSON."""
    if isinstance(data, dict):
        return {k.strip(): clean_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_data(item) for item in data]
    elif isinstance(data, str):
        return data.strip()
    return data


async def seed_database():
    async with AsyncSessionLocal() as db:
        # 1. Проверяем, есть ли уже продукты
        product_count = await db.scalar(select(func.count(Product.id)))
        if product_count > 0:
            print(f"✅ В базе уже {product_count} продуктов. Пропускаем seeding.")
            return

        print("🌱 Заполняем базу начальными данными...")

        # 2. Создаём категории
        categories_data = [
            {"name": "Оклейка пленкой", "slug": "wrapping", "sort_order": 1},
            {"name": "Химчистка", "slug": "cleaning", "sort_order": 2},
            {"name": "Детейлинг", "slug": "detailing", "sort_order": 3},
        ]
        
        categories = {}
        for cat_data in categories_data:
            stmt = select(Category).where(Category.slug == cat_data["slug"])
            result = await db.execute(stmt)
            category = result.scalars().first()
            
            if not category:
                category = Category(
                    name=cat_data["name"],
                    slug=cat_data["slug"],
                    is_active=True,
                    sort_order=cat_data["sort_order"],
                    description=None,
                    icon_url=None
                )
                db.add(category)
                await db.flush()
            categories[cat_data["slug"]] = category

        # 3. Загружаем продукты из products.json
        # Путь: от /app/app/seed.py поднимаемся на 2 уровня вверх до /app
        products_file = Path("/app/products.json")
        
        if not products_file.exists():
            print(f"⚠️  Файл {products_file} не найден. Пропускаем импорт продуктов.")
            print("💡 Убедитесь, что в Dockerfile есть: COPY products.json ./products.json")
        else:
            print(f"📂 Загружаем: {products_file}")
            with open(products_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            
            # 🔑 КРИТИЧНО: ваш JSON имеет пробелы в ключах. Функция чистит их на лету.
            products_data = clean_json_data(raw_data)
            print(f"📦 Найдено {len(products_data)} продуктов в JSON")
            
            for p in products_data:
                slug = p.get("slug", "")
                if not slug:
                    print(f"⚠️  Пропущен продукт без slug: {p.get('title')}")
                    continue
                
                # Пропускаем дубликаты
                stmt = select(Product).where(Product.slug == slug)
                if (await db.execute(stmt)).scalars().first():
                    continue
                
                # Безопасный маппинг Enum
                try:
                    product_type = ProductType(p.get("product_type", "SERVICE").upper())
                except ValueError:
                    product_type = ProductType.SERVICE
                    
                try:
                    status = ProductStatus(p.get("status", "ACTIVE").upper())
                except ValueError:
                    status = ProductStatus.ACTIVE
                
                # Очистка gallery: убираем ["string"], пустые строки и None
                gallery = p.get("gallery", [])
                if isinstance(gallery, list):
                    gallery = [g for g in gallery if g and g.lower() != "string"]
                    gallery = gallery if gallery else None
                
                # Определяем category_id (фоллбэк на первую категорию, если в JSON пусто)
                cat_id = p.get("category_id")
                if not cat_id:
                    cat_id = next(iter(categories.values())).id
                
                # Создаём продукт (id генерируется БД автоматически, чтобы не ломать sequence)
                product = Product(
                    title=p.get("title", "Без названия"),
                    slug=slug,
                    description=p.get("description"),
                    price=float(p.get("price", 0)),
                    currency=p.get("currency", "RUB"),
                    product_type=product_type,
                    status=status,
                    image_url=p.get("image_url"),
                    gallery=gallery,
                    category_id=int(cat_id),
                    is_featured=bool(p.get("is_featured", False)),
                    sort_order=int(p.get("sort_order", 0)),
                )
                db.add(product)
            
            print(f"✅ Продукты из JSON успешно добавлены")

        # 4. Создаём тестового админа
        stmt = select(User).where(User.telegram_id == 1864568706)
        result = await db.execute(stmt)
        if not result.scalars().first():
            admin_user = User(
                telegram_id=1864568706,
                username="makcsoop",
                first_name="Админ",
                last_name=None,
                language_code="ru",
                is_premium=False,
                role=UserRole.ADMIN
            )
            db.add(admin_user)
            print("✅ Добавлен тестовый админ")

        # 5. Коммитим все изменения
        await db.commit()
        print("✅ Начальные данные успешно добавлены!")


if __name__ == "__main__":
    asyncio.run(seed_database())