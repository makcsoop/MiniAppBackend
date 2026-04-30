# backend/seed.py
import asyncio
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.product import Product, ProductType, ProductStatus

async def seed_database():
    async with AsyncSessionLocal() as db:
        # 1. Проверяем, есть ли уже данные (чтобы не дублировать)
        cat_count = await db.scalar(select(func.count(Category.id)))
        if cat_count > 0:
            print("✅ База данных уже заполнена. Пропускаем seeding.")
            return

        print("🌱 Заполняем базу начальными данными...")

        # 2. Категории
        categories = [
            Category(name="Оклейка пленкой", slug="wrapping", is_active=True, sort_order=1),
            Category(name="Химчистка", slug="cleaning", is_active=True, sort_order=2),
            Category(name="Детейлинг", slug="detailing", is_active=True, sort_order=3),
        ]
        db.add_all(categories)
        await db.flush()  # Чтобы получить id для продуктов

        # 3. Продукты (ссылки на placeholder-картинки для теста)
        products = [
            Product(
                title="Полная оклейка матовой пленкой",
                slug="full-matte-wrap",
                price=150000.0,
                currency="RUB",
                product_type=ProductType.SERVICE,
                status=ProductStatus.ACTIVE,
                category_id=categories[0].id,
                image_url="https://placehold.co/600x400/222/fff?text=Matte+Wrap"
            ),
            Product(
                title="Химчистка салона (стандарт)",
                slug="standard-cleaning",
                price=8000.0,
                currency="RUB",
                product_type=ProductType.SERVICE,
                status=ProductStatus.ACTIVE,
                category_id=categories[1].id,
                image_url="https://placehold.co/600x400/1a1a1a/fff?text=Cleaning"
            ),
            Product(
                title="Полировка кузова",
                slug="polishing",
                price=12000.0,
                currency="RUB",
                product_type=ProductType.SERVICE,
                status=ProductStatus.ACTIVE,
                category_id=categories[2].id,
                image_url="https://placehold.co/600x400/333/fff?text=Polish"
            ),
        ]
        db.add_all(products)

        # 4. Тестовый админ (замените telegram_id на свой после первого входа)
        admin_user = User(
            telegram_id=1864568706,  # 👈 Замените на ваш реальный ID после /start в боте
            username="makcsoop",
            first_name="Админ",
            role=UserRole.ADMIN
        )
        db.add(admin_user)

        await db.commit()
        print("✅ Начальные данные успешно добавлены!")

if __name__ == "__main__":
    asyncio.run(seed_database())