# bot/handlers/products.py
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from bot.database import AsyncSessionLocal
from bot.handlers.common import ensure_admin, form_keyboard, remove_keyboard, slugify
from bot.models import Category, Product, ProductStatus, ProductType
from bot.states import ProductForm

router = Router()

@router.callback_query(F.data == "admin:products")
async def list_products(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        prods = (
            await db.execute(
                select(Product).options(selectinload(Product.category)).order_by(Product.created_at.desc()).limit(25)
            )
        ).scalars().all()

    lines = ["🛍️ Услуги/Товары", ""]
    if not prods:
        lines.append("Пока нет записей.")
    else:
        for p in prods:
            status = "✅" if p.status == ProductStatus.ACTIVE else ("📝" if p.status == ProductStatus.DRAFT else "📦")
            category = p.category.name if p.category else "Без категории"
            lines.append(f"{status} {p.title} ({p.price} {p.currency}) • {category}")

    b = InlineKeyboardBuilder()
    for p in prods:
        status = "✅" if p.status == ProductStatus.ACTIVE else ("📝" if p.status == ProductStatus.DRAFT else "📦")
        b.row(InlineKeyboardButton(text=f"{status} {p.title}", callback_data=f"admin:prod:{p.id}"))
    b.row(InlineKeyboardButton(text="➕ Добавить", callback_data="admin:prod:add"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    await cb.message.edit_text("\n".join(lines), reply_markup=b.as_markup())
    await cb.answer()


@router.callback_query(F.data == "admin:prod:add")
async def product_create_start(cb: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
    await state.set_state(ProductForm.title)
    await state.update_data(editing_product_id=None)
    await cb.message.answer("Название услуги/товара:", reply_markup=form_keyboard(["🔙 Отмена"]))
    await cb.answer()


@router.callback_query(F.data.startswith("admin:prod:edit:"))
async def product_edit_start(cb: CallbackQuery, state: FSMContext):
    pid = int(cb.data.split(":")[-1])
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        product = await db.get(Product, pid)
        if not product:
            await cb.answer("❌ Услуга не найдена", show_alert=True)
            return
    await state.set_state(ProductForm.title)
    await state.update_data(
        editing_product_id=pid,
        title=product.title,
        slug=product.slug,
        description=product.description,
        price=product.price,
        currency=product.currency,
        product_type=product.product_type.value,
        status=product.status.value,
        category_id=product.category_id,
        image_url=product.image_url,
        is_featured=product.is_featured,
        sort_order=product.sort_order,
    )
    await cb.message.answer("Новое название (или `.` чтобы оставить текущее):", reply_markup=form_keyboard(["."]))
    await cb.answer()


@router.message(ProductForm.title)
async def product_title(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text != ".":
        await state.update_data(title=text)
    await state.set_state(ProductForm.slug)
    await msg.answer("Slug (или `auto`/`.`):", reply_markup=form_keyboard(["auto", "."]))


@router.message(ProductForm.slug)
async def product_slug(msg: Message, state: FSMContext):
    data = await state.get_data()
    text = (msg.text or "").strip().lower()
    if text == "auto":
        await state.update_data(slug=slugify(data["title"]))
    elif text != ".":
        await state.update_data(slug=slugify(text))
    await state.set_state(ProductForm.description)
    await msg.answer("Описание (или `-`/`.`):", reply_markup=form_keyboard(["-", "."]))


@router.message(ProductForm.description)
async def product_description(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text == "-":
        await state.update_data(description=None)
    elif text != ".":
        await state.update_data(description=text)
    await state.set_state(ProductForm.price)
    await msg.answer("Цена (число):", reply_markup=form_keyboard(["1000", "2500", "5000", "."]))


@router.message(ProductForm.price)
async def product_price(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text != ".":
        try:
            await state.update_data(price=round(float(text.replace(",", ".")), 2))
        except ValueError:
            await msg.answer("Введите корректную цену.")
            return
    await state.set_state(ProductForm.currency)
    await msg.answer("Валюта (ISO, напр. RUB):", reply_markup=form_keyboard(["RUB", "USD", "EUR", "."]))


@router.message(ProductForm.currency)
async def product_currency(msg: Message, state: FSMContext):
    text = (msg.text or "").strip().upper()
    if text != ".":
        if len(text) != 3:
            await msg.answer("Код валюты должен содержать 3 символа.")
            return
        await state.update_data(currency=text)
    await state.set_state(ProductForm.product_type)
    await msg.answer("Тип:", reply_markup=form_keyboard(["service", "product", "."]))


@router.message(ProductForm.product_type)
async def product_type(msg: Message, state: FSMContext):
    text = (msg.text or "").strip().lower()
    if text != ".":
        if text not in {"service", "product"}:
            await msg.answer("Выберите `service` или `product`.")
            return
        await state.update_data(product_type=text)
    await state.set_state(ProductForm.status)
    await msg.answer("Статус:", reply_markup=form_keyboard(["draft", "active", "archived", "."]))


@router.message(ProductForm.status)
async def product_status(msg: Message, state: FSMContext):
    text = (msg.text or "").strip().lower()
    if text != ".":
        if text not in {"draft", "active", "archived"}:
            await msg.answer("Выберите статус: draft/active/archived.")
            return
        await state.update_data(status=text)
    await state.set_state(ProductForm.category_id)
    await msg.answer("ID категории (или `-`/`.`):", reply_markup=form_keyboard(["-", "."]))


@router.message(ProductForm.category_id)
async def product_category(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text == "-":
        await state.update_data(category_id=None)
    elif text != ".":
        try:
            await state.update_data(category_id=int(text))
        except ValueError:
            await msg.answer("Введите числовой ID или `-`.")
            return
    await state.set_state(ProductForm.image_url)
    await msg.answer("Ссылка на изображение (или `-`/`.`):", reply_markup=form_keyboard(["-", "."]))


@router.message(ProductForm.image_url)
async def product_image(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text == "-":
        await state.update_data(image_url=None)
    elif text != ".":
        await state.update_data(image_url=text)
    await state.set_state(ProductForm.is_featured)
    await msg.answer("Показывать в избранном?", reply_markup=form_keyboard(["yes", "no", "."]))


@router.message(ProductForm.is_featured)
async def product_featured(msg: Message, state: FSMContext):
    text = (msg.text or "").strip().lower()
    if text != ".":
        if text not in {"yes", "no"}:
            await msg.answer("Выберите yes/no.")
            return
        await state.update_data(is_featured=text == "yes")
    await state.set_state(ProductForm.sort_order)
    await msg.answer("Порядок сортировки:", reply_markup=form_keyboard(["0", "10", "20", "."]))


@router.message(ProductForm.sort_order)
async def product_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    text = (msg.text or "").strip()
    if text != ".":
        try:
            data["sort_order"] = int(text)
        except ValueError:
            await msg.answer("Нужно целое число.")
            return

    payload = {
        "title": data["title"],
        "slug": data["slug"],
        "description": data.get("description"),
        "price": data["price"],
        "currency": data.get("currency", "RUB"),
        "product_type": ProductType(data.get("product_type", "service")),
        "status": ProductStatus(data.get("status", "draft")),
        "category_id": data.get("category_id"),
        "image_url": data.get("image_url"),
        "is_featured": bool(data.get("is_featured", False)),
        "sort_order": int(data.get("sort_order", 0)),
    }

    async with AsyncSessionLocal() as db:
        if payload["category_id"] is not None:
            exists_cat = await db.get(Category, payload["category_id"])
            if not exists_cat:
                await msg.answer("Категория с таким ID не найдена.")
                return
        existing_slug = (
            await db.execute(select(Product).where(Product.slug == payload["slug"]))
        ).scalar_one_or_none()
        editing_id = data.get("editing_product_id")
        if existing_slug and existing_slug.id != editing_id:
            await msg.answer("Slug уже используется другой услугой.")
            return

        if editing_id:
            await db.execute(update(Product).where(Product.id == editing_id).values(**payload))
            await db.commit()
            result_text = "✅ Услуга обновлена."
        else:
            db.add(Product(**payload))
            await db.commit()
            result_text = "✅ Услуга создана."
    await state.clear()
    await msg.answer(result_text, reply_markup=remove_keyboard())


@router.callback_query(F.data.startswith("admin:prod:"))
async def product_actions_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return

    if len(parts) == 3:
        pid = int(parts[2])
        async with AsyncSessionLocal() as db:
            p = (
                await db.execute(
                    select(Product).options(selectinload(Product.category)).where(Product.id == pid)
                )
            ).scalar_one_or_none()
        if not p:
            await cb.answer("❌ Продукт не найден", show_alert=True)
            return
        cat_name = p.category.name if p.category else "Без категории"
        b = InlineKeyboardBuilder()
        next_status = ProductStatus.ARCHIVED if p.status == ProductStatus.ACTIVE else ProductStatus.ACTIVE
        status_text = "📦 Архивировать" if p.status == ProductStatus.ACTIVE else "🌍 Опубликовать"
        b.row(InlineKeyboardButton(text=status_text, callback_data=f"admin:prod:status:{p.id}:{next_status.value}"))
        b.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:prod:edit:{p.id}"))
        b.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:prod:del:{p.id}"))
        b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:products"))
        await cb.message.edit_text(
            f"🛍️ {p.title}\nSlug: {p.slug}\nЦена: {p.price} {p.currency}\nТип: {p.product_type.value}\n"
            f"Статус: {p.status.value}\nКатегория: {cat_name}\nИзбранное: {'Да' if p.is_featured else 'Нет'}",
            reply_markup=b.as_markup(),
        )
        await cb.answer()

    elif len(parts) == 5 and parts[2] == "status":
        pid, new_status = int(parts[3]), parts[4]
        async with AsyncSessionLocal() as db:
            await db.execute(update(Product).where(Product.id == pid).values(status=ProductStatus(new_status)))
            await db.commit()
        await cb.answer("✅ Статус изменен")
        await list_products(cb)

    elif len(parts) == 4 and parts[2] == "del":
        pid = int(parts[3])
        async with AsyncSessionLocal() as db:
            await db.execute(delete(Product).where(Product.id == pid))
            await db.commit()
        await cb.answer("🗑 Услуга удалена")
        await list_products(cb)

    await cb.answer()