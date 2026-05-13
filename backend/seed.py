# backend/app/seed.py
import asyncio
import json
import re
from pathlib import Path
from sqlalchemy import select, func
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.category import Category
from app.models.product import Product, ProductType, ProductStatus
from app.models.car import CarBrand, CarModel


def slugify(text: str) -> str:
    """Превращает 'Toyota Camry' в 'toyota-camry'"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)


def clean_json_data(data):
    """Рекурсивно убирает пробелы из ключей и строковых значений JSON."""
    if isinstance(data, dict):
        return {k.strip(): clean_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_json_data(item) for item in data]
    elif isinstance(data, str):
        return data.strip()
    return data


# =============================================================================
# === НАЧАЛЬНЫЕ ДАННЫЕ ДЛЯ АВТО ===
# =============================================================================

CAR_BRANDS = [
    "Toyota", "BMW", "Mercedes", "Audi", "Volkswagen", "Hyundai", "Kia",
]

MODELS_BY_BRAND: dict[str, list[str]] = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Land Cruiser", "Highlander", "C-HR", "Yaris"],
    "BMW": ["3 серия", "5 серия", "X3", "X5", "X1", "1 серия"],
    "Mercedes": ["C-класс", "E-класс", "GLC", "GLE", "A-класс"],
    "Audi": ["A4", "A6", "Q5", "Q7", "A3", "Q3"],
    "Volkswagen": ["Polo", "Jetta", "Tiguan", "Passat", "Touareg", "Golf"],
    "Hyundai": ["Solaris", "Creta", "Tucson", "Santa Fe", "Elantra"],
    "Kia": ["Rio", "Sportage", "Sorento", "Cerato", "Optima"],
    "_default": ["Седан", "Хэтчбек", "Универсал", "Кроссовер", "Минивэн", "Пикап"],
}


async def seed_cars(db):
    """Заполняет таблицы car_brands и car_models начальными данными"""
    brand_count = await db.scalar(select(func.count(CarBrand.id)))
    if brand_count > 0:
        print(f"✅ В базе уже {brand_count} марок авто. Пропускаем.")
        return
    
    print("🚗 Заполняем марки и модели авто...")
    brands_map = {}
    
    for brand_name in CAR_BRANDS:
        slug = slugify(brand_name)
        stmt = select(CarBrand).where(CarBrand.slug == slug)
        result = await db.execute(stmt)
        brand = result.scalars().first()
        
        if not brand:
            brand = CarBrand(name=brand_name, slug=slug)
            db.add(brand)
            await db.flush()
            print(f"  + Марка: {brand_name}")
        brands_map[slug] = brand.id
    
    for brand_name, models in MODELS_BY_BRAND.items():
        if brand_name == "_default":
            continue
        brand_slug = slugify(brand_name)
        brand_id = brands_map.get(brand_slug)
        if not brand_id:
            continue
        
        for model_name in models:
            model_slug = slugify(f"{brand_name}-{model_name}")
            stmt = select(CarModel).where(CarModel.slug == model_slug)
            result = await db.execute(stmt)
            if result.scalars().first():
                continue
            model = CarModel(name=model_name, slug=model_slug, brand_id=brand_id)
            db.add(model)
        print(f"  + Модели для {brand_name}: {len(models)}")
    
    print("✅ Марки и модели авто успешно добавлены!")


async def seed_database():
    async with AsyncSessionLocal() as db:
        with db.no_autoflush:
            # =================================================================
            # === 1. КАТЕГОРИИ — всегда загружаем в dict, даже если уже есть ===
            # =================================================================
            print("📁 Создаём/загружаем категории...")
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
                        name=cat_data["name"], slug=cat_data["slug"],
                        is_active=True, sort_order=cat_data["sort_order"],
                        description=None, icon_url=None
                    )
                    db.add(category)
                    await db.flush()  # Получаем category.id сразу
                
                # 👇 КЛЮЧЕВОЕ: добавляем в словарь ВСЕГДА, не только при создании
                categories[cat_data["slug"]] = category
            
            await db.commit()
            print(f"✅ Категории готовы: {list(categories.keys())}")

            # =================================================================
            # === 2. ПРОДУКТЫ ===
            # =================================================================
            product_count = await db.scalar(select(func.count(Product.id)))
            if product_count > 0:
                print(f"✅ В базе уже {product_count} продуктов. Пропускаем.")
            else:
                print("📦 Загружаем продукты из JSON...")
                products_file = Path("/app/products.json")
                
                if products_file.exists():
                    with open(products_file, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    
                    products_data = clean_json_data(raw_data)
                    
                    # 👇 Получаем первую категорию для фоллбэка (безопасно)
                    first_category = next(iter(categories.values()), None)
                    if not first_category:
                        print("⚠️  Нет категорий! Пропускаем импорт продуктов.")
                        return
                    
                    for p in products_data:
                        slug = p.get("slug", "")
                        if not slug:
                            continue
                        
                        stmt = select(Product).where(Product.slug == slug)
                        if (await db.execute(stmt)).scalars().first():
                            continue
                        
                        try:
                            product_type = ProductType(p.get("product_type", "SERVICE").upper())
                        except ValueError:
                            product_type = ProductType.SERVICE
                        try:
                            status = ProductStatus(p.get("status", "ACTIVE").upper())
                        except ValueError:
                            status = ProductStatus.ACTIVE
                        
                        gallery = p.get("gallery", [])
                        if isinstance(gallery, list):
                            gallery = [g for g in gallery if g and g.lower() != "string"]
                            gallery = gallery if gallery else None
                        
                        # 👇 Безопасное получение category_id
                        cat_slug = p.get("category_slug", "wrapping")
                        cat = categories.get(cat_slug) or first_category
                        
                        product = Product(
                            title=p.get("title", "Без названия"), slug=slug,
                            description=p.get("description"), price=float(p.get("price", 0)),
                            currency=p.get("currency", "RUB"), product_type=product_type,
                            status=status, image_url=p.get("image_url"), gallery=gallery,
                            category_id=cat.id,  # 👈 Гарантированно существующий ID
                            is_featured=bool(p.get("is_featured", False)),
                            sort_order=int(p.get("sort_order", 0)),
                        )
                        db.add(product)
                    
                    await db.commit()
                    print(f"✅ Продукты из JSON успешно добавлены")

            # =================================================================
            # === 3. АВТО ===
            # =================================================================
            await seed_cars(db)
            await db.commit()

            # =================================================================
            # === 4. АДМИН ===
            # =================================================================
            stmt = select(User).where(User.telegram_id == 1864568706)
            result = await db.execute(stmt)
            if not result.scalars().first():
                admin_user = User(
                    telegram_id=1864568706, username="makcsoop",
                    first_name="Админ", last_name=None, language_code="ru",
                    is_premium=False, role=UserRole.ADMIN
                )
                db.add(admin_user)
                await db.commit()
                print("✅ Добавлен тестовый админ")

        print("✅✅✅ Все начальные данные успешно добавлены! ✅✅✅")


if __name__ == "__main__":
    asyncio.run(seed_database())