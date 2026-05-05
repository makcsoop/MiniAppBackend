# bot/handlers/categories.py
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, delete

from bot.database import AsyncSessionLocal
from bot.handlers.common import ensure_admin, form_keyboard, remove_keyboard, slugify
from bot.models import Category
from bot.states import CategoryForm

router = Router()

@router.callback_query(F.data == "admin:categories")
async def list_categories(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        cats = (await db.execute(select(Category).order_by(Category.sort_order, Category.name))).scalars().all()

    text = ["📁 Категории", ""]
    if not cats:
        text.append("Пока нет категорий.")
    for c in cats:
        text.append(f"{'✅' if c.is_active else '❌'} {c.name} ({c.slug})")

    b = InlineKeyboardBuilder()
    for c in cats:
        b.row(InlineKeyboardButton(text=f"{'✅' if c.is_active else '❌'} {c.name}", callback_data=f"admin:cat:{c.id}"))
    b.row(InlineKeyboardButton(text="➕ Добавить", callback_data="admin:cat:add"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    await cb.message.edit_text("\n".join(text), reply_markup=b.as_markup())
    await cb.answer()


@router.callback_query(F.data == "admin:cat:add")
async def start_create_category(cb: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
    await state.set_state(CategoryForm.name)
    await cb.message.answer("Введите название категории:", reply_markup=form_keyboard(["🔙 Отмена"]))
    await cb.answer()


@router.message(CategoryForm.name)
async def category_name(msg: Message, state: FSMContext):
    if msg.text == "🔙 Отмена":
        await state.clear()
        await msg.answer("Операция отменена.", reply_markup=remove_keyboard())
        return
    await state.update_data(name=(msg.text or "").strip())
    await state.set_state(CategoryForm.slug)
    await msg.answer("Введите slug или `auto` для автогенерации.")


@router.message(CategoryForm.slug)
async def category_slug(msg: Message, state: FSMContext):
    data = await state.get_data()
    raw = (msg.text or "").strip().lower()
    slug = slugify(data.get("name", "")) if raw == "auto" else slugify(raw)
    await state.update_data(slug=slug)
    await state.set_state(CategoryForm.description)
    await msg.answer("Описание (или `-` чтобы пропустить):")


@router.message(CategoryForm.description)
async def category_description(msg: Message, state: FSMContext):
    description = None if (msg.text or "").strip() == "-" else (msg.text or "").strip()
    await state.update_data(description=description)
    await state.set_state(CategoryForm.icon_url)
    await msg.answer("Ссылка на иконку (или `-` чтобы пропустить):")


@router.message(CategoryForm.icon_url)
async def category_icon(msg: Message, state: FSMContext):
    icon_url = None if (msg.text or "").strip() == "-" else (msg.text or "").strip()
    await state.update_data(icon_url=icon_url)
    await state.set_state(CategoryForm.sort_order)
    await msg.answer("Порядок сортировки (число, по умолчанию 0):", reply_markup=form_keyboard(["0", "10", "20"]))


@router.message(CategoryForm.sort_order)
async def category_save(msg: Message, state: FSMContext):
    try:
        sort_order = int((msg.text or "0").strip())
    except ValueError:
        await msg.answer("Введите целое число.")
        return
    data = await state.get_data()
    async with AsyncSessionLocal() as db:
        exists = (
            await db.execute(
                select(Category).where((Category.slug == data["slug"]) | (Category.name == data["name"]))
            )
        ).scalar_one_or_none()
        if exists:
            await msg.answer("Категория с таким именем или slug уже существует.")
            return
        db.add(
            Category(
                name=data["name"],
                slug=data["slug"],
                description=data.get("description"),
                icon_url=data.get("icon_url"),
                sort_order=sort_order,
                is_active=True,
            )
        )
        await db.commit()
    await state.clear()
    await msg.answer("✅ Категория создана.", reply_markup=remove_keyboard())


@router.callback_query(F.data.startswith("admin:cat:"))
async def category_actions_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return

    if len(parts) == 3:
        cid = int(parts[2])
        async with AsyncSessionLocal() as db:
            c = await db.get(Category, cid)
        if not c:
            await cb.answer("❌ Категория не найдена", show_alert=True)
            return
        b = InlineKeyboardBuilder()
        action = "deactivate" if c.is_active else "activate"
        b.row(InlineKeyboardButton(text="🔴 Деактивировать" if c.is_active else "🟢 Активировать", callback_data=f"admin:cat:toggle:{c.id}:{action}"))
        b.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:cat:del:{c.id}"))
        b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:categories"))
        await cb.message.edit_text(
            f"📁 {c.name}\nSlug: {c.slug}\nОписание: {c.description or '—'}\nПорядок: {c.sort_order}\nАктивна: {'Да' if c.is_active else 'Нет'}",
            reply_markup=b.as_markup(),
        )
        await cb.answer()

    elif len(parts) == 5 and parts[2] == "toggle":
        cid, action = int(parts[3]), parts[4]
        async with AsyncSessionLocal() as db:
            await db.execute(update(Category).where(Category.id == cid).values(is_active=(action == "activate")))
            await db.commit()
        await cb.answer("✅ Изменения сохранены")
        await list_categories(cb)

    elif len(parts) == 4 and parts[2] == "del":
        cid = int(parts[3])
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Category).where(Category.id == cid))
            await db.commit()
        await cb.answer("🗑 Категория удалена")
        await list_categories(cb)

    await cb.answer()