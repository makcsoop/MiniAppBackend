# bot/handlers/brands.py
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, delete, func

from bot.database import AsyncSessionLocal
from bot.handlers.common import clear_stale_reply_keyboard, ensure_admin, form_keyboard, remove_keyboard, slugify
from bot.models import CarBrand, CarModel
from bot.states import BrandForm

router = Router()


@router.callback_query(F.data == "admin:brands")
async def list_brands(cb: CallbackQuery):
    await clear_stale_reply_keyboard(cb.message)
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        brands = (await db.execute(select(CarBrand).order_by(CarBrand.name))).scalars().all()

    text = ["🚗 Марки авто", ""]
    if not brands:
        text.append("Пока нет марок.")
    for b in brands:
        text.append(f"• {b.name} ({b.slug})")

    kb = InlineKeyboardBuilder()
    for b in brands:
        kb.row(InlineKeyboardButton(text=b.name, callback_data=f"admin:brand:{b.id}"))
    kb.row(InlineKeyboardButton(text="➕ Добавить", callback_data="admin:brand:add"))
    kb.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    await cb.message.edit_text("\n".join(text), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "admin:brand:add")
async def start_create_brand(cb: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
    await state.set_state(BrandForm.name)
    await state.update_data(editing_brand_id=None)
    await cb.message.answer("Введите название марки:", reply_markup=form_keyboard(["🔙 Отмена"]))
    await cb.answer()


@router.callback_query(F.data.startswith("admin:brand:edit:"))
async def start_edit_brand(cb: CallbackQuery, state: FSMContext):
    bid = int(cb.data.split(":")[-1])
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        brand = await db.get(CarBrand, bid)
        if not brand:
            await cb.answer("❌ Марка не найдена", show_alert=True)
            return
    await state.set_state(BrandForm.name)
    await state.update_data(editing_brand_id=bid, name=brand.name, slug=brand.slug)
    await cb.message.answer("Новое название (или `.` чтобы оставить):", reply_markup=form_keyboard(["."]))
    await cb.answer()


@router.message(BrandForm.name)
async def brand_name(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text == "🔙 Отмена":
        await state.clear()
        await msg.answer("Операция отменена.", reply_markup=remove_keyboard())
        return
    if text != ".":
        await state.update_data(name=text)
    await state.set_state(BrandForm.slug)
    await msg.answer("Slug (или `auto`/`.`):", reply_markup=form_keyboard(["auto", "."]))


@router.message(BrandForm.slug)
async def brand_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    text = (msg.text or "").strip().lower()
    if text == "auto":
        slug = slugify(data["name"])
    elif text != ".":
        slug = slugify(text)
    else:
        slug = data["slug"]

    payload = {"name": data["name"], "slug": slug}
    editing_id = data.get("editing_brand_id")

    async with AsyncSessionLocal() as db:
        conflict = (
            await db.execute(
                select(CarBrand).where(
                    (CarBrand.slug == payload["slug"]) | (CarBrand.name == payload["name"])
                )
            )
        ).scalar_one_or_none()
        if conflict and conflict.id != editing_id:
            await msg.answer("Марка с таким именем или slug уже существует.")
            return

        if editing_id:
            await db.execute(update(CarBrand).where(CarBrand.id == editing_id).values(**payload))
            await db.commit()
            result_text = "✅ Марка обновлена."
        else:
            db.add(CarBrand(**payload))
            await db.commit()
            result_text = "✅ Марка создана."

    await state.clear()
    await msg.answer(result_text, reply_markup=remove_keyboard())


@router.callback_query(F.data.startswith("admin:brand:"))
async def brand_actions_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return

    if len(parts) == 3 and parts[2].isdigit():
        bid = int(parts[2])
        brand = await db.get(CarBrand, bid)
        if not brand:
            await cb.answer("❌ Марка не найдена", show_alert=True)
            return
        models_count = await db.scalar(
            select(func.count(CarModel.id)).where(CarModel.brand_id == bid)
        )
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🔧 Модели марки", callback_data=f"admin:brand:models:{bid}"))
        kb.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:brand:edit:{bid}"))
        kb.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:brand:del:{bid}"))
        kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:brands"))
        await cb.message.edit_text(
            f"🚗 {brand.name}\nSlug: {brand.slug}\nМоделей: {models_count or 0}",
            reply_markup=kb.as_markup(),
        )
        await cb.answer()
        return

    if len(parts) == 4 and parts[2] == "del" and parts[3].isdigit():
        bid = int(parts[3])
        await db.execute(delete(CarBrand).where(CarBrand.id == bid))
        await db.commit()
        await cb.answer("🗑 Марка удалена")
        await list_brands(cb)
        return

    await cb.answer()
