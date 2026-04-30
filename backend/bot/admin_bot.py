# bot/admin_bot.py
import asyncio
import logging
import html
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest  # 👈 Добавлено для обработки ошибки
from bot.config import settings
from bot.database import AsyncSessionLocal
from bot.models import User, Category, Product, UserRole, ProductStatus, ProductType
from sqlalchemy import select, update, func, delete
from sqlalchemy.orm import selectinload

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# ==================== FSM ====================
class AddCategoryState(StatesGroup):
    name = State()
    slug = State()

class AddProductState(StatesGroup):
    title = State()
    slug = State()
    price = State()
    image_url = State()
    product_type = State()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
async def safe_edit(message, text: str, reply_markup=None):
    """Безопасное редактирование сообщения: игнорирует ошибку 'message is not modified'"""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

async def is_admin(user_id: int) -> bool:
    if user_id in settings.admin_ids_list:
        return True
    async with AsyncSessionLocal() as db:
        stmt = select(User).where(User.telegram_id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        return user and user.role == "ADMIN"

def escape_md(text: str) -> str:
    return html.escape(str(text)).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')

def main_menu_kb():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"))
    b.row(InlineKeyboardButton(text="📁 Категории", callback_data="admin:categories"))
    b.row(InlineKeyboardButton(text="🛍️ Продукты", callback_data="admin:products"))
    b.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:refresh"))
    return b.as_markup()

def remove_keyboard():
    """Убирает быстрые кнопки и возвращает обычную клавиатуру"""
    return ReplyKeyboardRemove()

def get_quick_buttons_kb():
    """Клавиатура с быстрыми ответами (исчезает после одного нажатия)"""
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🖼️ Пример картинки"), KeyboardButton(text="⏭️ Пропустить")],
            [KeyboardButton(text="1️⃣ Услуга"), KeyboardButton(text="2️⃣ Товар")],
            [KeyboardButton(text="🔙 Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,  # 👈 Клавиатура скроется после первого нажатия!
        input_field_placeholder="Выберите действие или введите текст"
    )
    return kb


# ==================== СТАРТ И МЕНЮ ====================
@dp.message(F.text == "🔙 Отмена")
async def cancel_handler(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Операция отменена", reply_markup=main_menu_kb())


@dp.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    if not await is_admin(msg.from_user.id):
        await msg.answer("❌ Доступ запрещен.")
        return
    await msg.answer("🛠️ Админ-панель СинтезКар\nВыберите раздел:", reply_markup=main_menu_kb())

@dp.callback_query(F.data.in_(["admin:menu", "admin:refresh"]))
async def show_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_edit(cb.message, "🛠️ Админ-панель СинтезКар\nВыберите раздел:", main_menu_kb())
    await cb.answer()


@dp.message(AddProductState.image_url)
async def handle_quick_image(msg: Message, state: FSMContext):
    if msg.text == "🖼️ Пример картинки":
        await msg.answer("https://placehold.co/600x400/1a1a1a/fff?text=Car+Wrap", reply_markup=get_quick_buttons_kb())
        return
    elif msg.text == "⏭️ Пропустить":
        await state.update_data(image_url=None)
        await state.set_state(AddProductState.product_type)
        await msg.answer("📝 Выберите тип продукта:\n1️⃣ Услуга (service)\n2️⃣ Товар (product)", reply_markup=get_quick_buttons_kb())
        return
    elif msg.text == "🔙 Отмена":
        await state.clear()
        await msg.answer("❌ Отменено", reply_markup=main_menu_kb())
        return
    
    # Обычная ссылка
    await state.update_data(image_url=msg.text.strip())
    await state.set_state(AddProductState.product_type)
    await msg.answer("📝 Выберите тип продукта:\n1️⃣ Услуга (service)\n2️⃣ Товар (product)", reply_markup=get_quick_buttons_kb())
    

# ==================== ПОЛЬЗОВАТЕЛИ ====================
@dp.callback_query(F.data == "admin:users")
async def list_users(cb: CallbackQuery, page: int = 1):
    async with AsyncSessionLocal() as db:
        total = await db.scalar(select(func.count(User.id)))
        users = (await db.execute(select(User).order_by(User.last_seen.desc()).offset((page-1)*10).limit(10))).scalars().all()
    
    lines = [f"{i}. {'👑' if u.role=='ADMIN' else '👤'} `{u.telegram_id}` — {escape_md(u.username or f'ID:{u.telegram_id}')}" for i, u in enumerate(users, start=(page-1)*10+1)]
    text = f"👥 Пользователи (стр. {page}, всего {total})\n\n" + "\n".join(lines) if lines else "👥 Пользователи\n\nПока нет пользователей."
    
    b = InlineKeyboardBuilder()
    for u in users:
        role = "👑" if u.role == "ADMIN" else "👤"
        b.row(InlineKeyboardButton(text=f"{role} {escape_md(u.username or u.telegram_id)}", callback_data=f"admin:user:{u.id}"))
    if page > 1: b.row(InlineKeyboardButton(text="⬅️", callback_data=f"admin:users:p:{page-1}"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    if len(users) == 10: b.row(InlineKeyboardButton(text="➡️", callback_data=f"admin:users:p:{page+1}"))
    
    await safe_edit(cb.message, text, b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("admin:user:"))
async def user_actions(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) == 3:
        async with AsyncSessionLocal() as db:
            u = await db.get(User, int(parts[2]))
        if not u: return await cb.answer("❌ Не найден", show_alert=True)
        text = f"👤 {escape_md(u.first_name or '—')} (@{escape_md(u.username or '—')})\nID: `{u.telegram_id}`\nРоль: `{u.role}`"
        b = InlineKeyboardBuilder()
        new_role = "USER" if u.role == "ADMIN" else "ADMIN"
        b.row(InlineKeyboardButton(text="👑 В админы" if new_role == "ADMIN" else "👤 В пользователи", callback_data=f"admin:user:role:{new_role}:{u.id}"))
        b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:users"))
        await safe_edit(cb.message, text, b.as_markup())
    elif len(parts) == 5 and parts[2] == "role":
        new_role, uid = parts[3], int(parts[4])
        async with AsyncSessionLocal() as db:
            await db.execute(update(User).where(User.id == uid).values(role=UserRole(new_role)))
            await db.commit()
        await cb.answer(f"✅ Роль изменена на {new_role}")
        await list_users(cb, page=1)
    await cb.answer()

@dp.callback_query(F.data.startswith("admin:users:p:"))
async def users_page(cb: CallbackQuery):
    await list_users(cb, int(cb.data.split(":")[-1]))

# ==================== КАТЕГОРИИ ====================
@dp.callback_query(F.data == "admin:categories")
async def list_categories(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        cats = (await db.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    
    lines = [f"{'✅' if c.is_active else '❌'} `{c.slug}` — {escape_md(c.name)}" for c in cats]
    text = "📁 Категории\n\n" + "\n".join(lines) if lines else "📁 Категории\n\nПока нет категорий."
    
    b = InlineKeyboardBuilder()
    for c in cats:
        b.row(InlineKeyboardButton(text=f"{'✅' if c.is_active else '❌'} {escape_md(c.name)}", callback_data=f"admin:cat:{c.id}"))
    b.row(InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin:cat:add"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    
    await safe_edit(cb.message, text, b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "admin:cat:add")
async def start_add_cat(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddCategoryState.name)
    await safe_edit(cb.message, "📝 Введите название новой категории:")
    await cb.answer()

@dp.message(AddCategoryState.name)
async def get_cat_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text)
    await state.set_state(AddCategoryState.slug)
    await msg.answer("📝 Теперь введите slug (например, wraps или okleyka):")

@dp.message(AddCategoryState.slug)
async def save_category(msg: Message, state: FSMContext):
    data = await state.get_data()
    slug = msg.text.strip().lower().replace(" ", "-")
    async with AsyncSessionLocal() as db:
        db.add(Category(name=data["name"], slug=slug))
        await db.commit()
    await state.clear()
    await msg.answer("✅ Категория добавлена!", reply_markup=main_menu_kb())

@dp.callback_query(F.data.startswith("admin:cat:"))
async def cat_actions(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) == 3:
        async with AsyncSessionLocal() as db:
            c = await db.get(Category, int(parts[2]))
        if not c: return await cb.answer("❌", show_alert=True)
        text = f"📁 {escape_md(c.name)}\nSlug: `{c.slug}`\nАктивна: {'✅' if c.is_active else '❌'}"
        b = InlineKeyboardBuilder()
        action = "deactivate" if c.is_active else "activate"
        b.row(InlineKeyboardButton(text="🔴 Деактивировать" if c.is_active else "🟢 Активировать", callback_data=f"admin:cat:toggle:{c.id}:{action}"))
        b.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:cat:del:{c.id}"))
        b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:categories"))
        await safe_edit(cb.message, text, b.as_markup())
    elif len(parts) == 4:
        if parts[2] == "toggle":
            cid, action = int(parts[3]), parts[4]
            async with AsyncSessionLocal() as db:
                await db.execute(update(Category).where(Category.id == cid).values(is_active=(action == "activate")))
                await db.commit()
            await cb.answer("✅ Обновлено")
            await list_categories(cb)
        elif parts[2] == "del":
            cid = int(parts[3])
            async with AsyncSessionLocal() as db:
                await db.execute(delete(Category).where(Category.id == cid))
                await db.commit()
            await cb.answer("🗑 Удалено")
            await list_categories(cb)
    await cb.answer()

# ==================== ПРОДУКТЫ ====================
@dp.callback_query(F.data == "admin:products")
async def list_products(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        # 👇 selectinload подгрузит категорию сразу, до закрытия сессии
        stmt = select(Product).options(selectinload(Product.category)).order_by(Product.id.desc()).limit(20)
        prods = (await db.execute(stmt)).scalars().all()
    
    lines = [f"{'✅' if p.status=='ACTIVE' else '⏸️'} `{escape_md(p.title)}` — {p.price} {p.currency}" for p in prods]
    text = "🛍️ Продукты\n\n" + "\n".join(lines) if lines else "🛍️ Продукты\n\nПока нет продуктов."
    
    b = InlineKeyboardBuilder()
    for p in prods:
        b.row(InlineKeyboardButton(text=f"{'✅' if p.status=='ACTIVE' else '⏸️'} {escape_md(p.title)}", callback_data=f"admin:prod:{p.id}"))
    b.row(InlineKeyboardButton(text="➕ Добавить продукт", callback_data="admin:prod:add"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    
    await safe_edit(cb.message, text, b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "admin:prod:add")
async def start_add_prod(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddProductState.title)
    await cb.message.edit_text("📝 Введите название продукта:", reply_markup=get_quick_buttons_kb())
    await cb.answer()

@dp.message(AddProductState.title)
async def get_prod_title(msg: Message, state: FSMContext):
    # Обработка кнопки "🔙 Отмена"
    if msg.text == "🔙 Отмена":
        await state.clear()
        await msg.answer("❌ Отменено", reply_markup=main_menu_kb())
        return
    
    await state.update_data(title=msg.text)
    await state.set_state(AddProductState.slug)
    # 👇 Показываем быстрые кнопки для следующего шага
    await msg.answer("📝 Введите slug (например, matovaya-plenka):", reply_markup=get_quick_buttons_kb())

@dp.message(AddProductState.slug)
async def get_prod_slug(msg: Message, state: FSMContext):
    if msg.text == "🔙 Отмена":
        await state.clear()
        await msg.answer("❌ Отменено", reply_markup=main_menu_kb())
        return
    
    await state.update_data(slug=msg.text.strip().lower().replace(" ", "-"))
    await state.set_state(AddProductState.price)
    await msg.answer("📝 Введите цену (только число, например 25000):", reply_markup=get_quick_buttons_kb())

@dp.message(AddProductState.price)
async def get_prod_price(msg: Message, state: FSMContext):
    if msg.text == "🔙 Отмена":
        await state.clear()
        await msg.answer("❌ Отменено", reply_markup=main_menu_kb())
        return
    
    try:
        price = float(msg.text.replace(",", "."))
        await state.update_data(price=price)
        await state.set_state(AddProductState.image_url)
        # 👇 Убираем старые кнопки, показываем новые для выбора фото
        await msg.answer(
            "📷 Введите ссылку на изображение (или отправьте `.` чтобы пропустить):\n\nПример: `https://placehold.co/600x400.png`",
            reply_markup=get_quick_buttons_kb()  # Новые кнопки для этого шага
        )
    except ValueError:
        await msg.answer("❌ Введите корректное число (например: 25000 или 25000.50)", reply_markup=get_quick_buttons_kb())

@dp.message(AddProductState.image_url)
async def get_prod_image(msg: Message, state: FSMContext):
    if msg.text == "🔙 Отмена":
        await state.clear()
        await msg.answer("❌ Отменено", reply_markup=main_menu_kb())
        return
    
    # Обработка кнопки "⏭️ Пропустить" или точки
    if msg.text in ["⏭️ Пропустить", "."]:
        await state.update_data(image_url=None)
    else:
        # Обработка кнопки с примером
        if msg.text == "🖼️ Пример картинки":
            await msg.answer("https://placehold.co/600x400/1a1a1a/fff?text=Car+Wrap", reply_markup=get_quick_buttons_kb())
            return
        await state.update_data(image_url=msg.text.strip())
    
    await state.set_state(AddProductState.product_type)
    # 👇 Показываем кнопки выбора типа
    await msg.answer(
        "📝 Выберите тип продукта:\n1️⃣ Услуга (service)\n2️⃣ Товар (product)\n\nОтправьте 1 или 2:",
        reply_markup=get_quick_buttons_kb()
    )

@dp.message(AddProductState.product_type)
async def save_product(msg: Message, state: FSMContext):
    if msg.text == "🔙 Отмена":
        await state.clear()
        await msg.answer("❌ Отменено", reply_markup=main_menu_kb())
        return
    
    data = await state.get_data()
    ptype = ProductType.SERVICE if msg.text.strip() == "1" else ProductType.PRODUCT
    
    product_data = {
        "title": data["title"],
        "slug": data["slug"],
        "price": data["price"],
        "currency": "RUB",
        "product_type": ptype,
        "status": ProductStatus.ACTIVE
    }
    if data.get("image_url"):
        product_data["image_url"] = data["image_url"]
    
    async with AsyncSessionLocal() as db:
        db.add(Product(**product_data))
        await db.commit()
    
    await state.clear()
    # 👇 КЛЮЧЕВОЕ: убираем ВСЕ быстрые кнопки и показываем главное меню
    await msg.answer("✅ Продукт добавлен!", reply_markup=main_menu_kb())

# ========= ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ ПРОДУКТА =========

@dp.message(AddProductState.title, lambda msg: msg.from_user.id in settings.admin_ids_list or True)  # Простая проверка
async def edit_prod_title(msg: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("editing_product_id")
    if not pid: return await msg.answer("❌ Ошибка: не указан продукт для редактирования")
    
    new_title = msg.text if msg.text.strip() != "." else None
    if new_title:
        await state.update_data(title=new_title)
        await state.set_state(AddProductState.slug)
        await msg.answer("📝 Введите новый slug (или `.` чтобы оставить без изменений):")
    else:
        await state.set_state(AddProductState.slug)
        await msg.answer("📝 Введите новый slug (или `.` чтобы оставить без изменений):")

@dp.message(AddProductState.slug, lambda msg: msg.from_user.id in settings.admin_ids_list or True)
async def edit_prod_slug(msg: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("editing_product_id")
    if not pid: return await msg.answer("❌ Ошибка")
    
    new_slug = msg.text.strip().lower().replace(" ", "-") if msg.text.strip() != "." else None
    if new_slug:
        await state.update_data(slug=new_slug)
        await state.set_state(AddProductState.price)
        await msg.answer("📝 Введите новую цену (или `.` чтобы оставить без изменений):")
    else:
        await state.set_state(AddProductState.price)
        await msg.answer("📝 Введите новую цену (или `.` чтобы оставить без изменений):")

@dp.message(AddProductState.price, lambda msg: msg.from_user.id in settings.admin_ids_list or True)
async def edit_prod_price(msg: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("editing_product_id")
    if not pid: return await msg.answer("❌ Ошибка")
    
    updates = {}
    if data.get("title") and msg.text.strip() != ".":
        updates["title"] = data["title"]
    if data.get("slug") and msg.text.strip() != ".":
        updates["slug"] = data["slug"]
    
    if msg.text.strip() != ".":
        try:
            updates["price"] = float(msg.text.replace(",", "."))
        except ValueError:
            return await msg.answer("❌ Введите корректное число")
    
    if updates:
        async with AsyncSessionLocal() as db:
            await db.execute(update(Product).where(Product.id == pid).values(**updates))
            await db.commit()
        await state.clear()
        await msg.answer("✅ Продукт обновлен!", reply_markup=main_menu_kb())
    else:
        await state.clear()
        await msg.answer("✅ Ничего не изменено", reply_markup=main_menu_kb())
    

@dp.callback_query(F.data.startswith("admin:prod:"))
async def prod_actions(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    
    # admin:prod:{id} — показать инфо + кнопки действий
    if len(parts) == 3:
        async with AsyncSessionLocal() as db:
            # 👇 selectinload подгрузит категорию сразу
            stmt = select(Product).options(selectinload(Product.category)).where(Product.id == int(parts[2]))
            result = await db.execute(stmt)
            p = result.scalars().first()
        
        if not p: return await cb.answer("❌ Продукт не найден", show_alert=True)
        
        cat_name = escape_md(p.category.name) if p.category else "Без категории"
        text = f"🛍️ {escape_md(p.title)}\n💰 Цена: `{p.price} {p.currency}`\n📊 Статус: `{p.status}`\n📁 Категория: {cat_name}"
        
        b = InlineKeyboardBuilder()
        # Кнопки действий
        new_st = "ARCHIVED" if p.status == "ACTIVE" else "ACTIVE"
        b.row(InlineKeyboardButton(text="📦 Скрыть" if p.status == "ACTIVE" else "🌍 Опубликовать", callback_data=f"admin:prod:status:{p.id}:{new_st}"))
        b.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:prod:edit:{p.id}"))  # 👈 Новая кнопка
        b.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:prod:del:{p.id}"))
        b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:products"))
        
        await safe_edit(cb.message, text, b.as_markup())
    
    # admin:prod:status:{id}:{new_status} — смена статуса
    elif len(parts) == 5 and parts[2] == "status":
        pid, new_st = int(parts[3]), parts[4]
        async with AsyncSessionLocal() as db:
            await db.execute(update(Product).where(Product.id == pid).values(status=ProductStatus(parts[4])))
            await db.commit()
        await cb.answer("✅ Статус изменен")
        await list_products(cb)
    
    # admin:prod:edit:{id} — начало редактирования
    elif len(parts) == 4 and parts[2] == "edit":
        pid = int(parts[3])
        await state.update_data(editing_product_id=pid)
        await state.set_state(AddProductState.title)  # Используем тот же FSM для простоты
        await cb.message.edit_text(f"✏️ **Редактирование продукта**\n\n📝 Введите новое название (или отправьте `.` чтобы оставить без изменений):", parse_mode="Markdown")
        await cb.answer()
    
    # admin:prod:del:{id} — удаление
    elif len(parts) == 4 and parts[2] == "del":
        pid = int(parts[3])
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Product).where(Product.id == pid))
            await db.commit()
        await cb.answer("🗑 Продукт удален")
        await list_products(cb)
    
    await cb.answer()

# ==================== ЗАПУСК ====================
async def main():
    me = await bot.get_me()
    logger.info(f"🤖 Bot @{me.username} started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())