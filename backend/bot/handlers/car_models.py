# bot/handlers/car_models.py
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from bot.database import AsyncSessionLocal
from bot.handlers.common import clear_stale_reply_keyboard, ensure_admin, form_keyboard, remove_keyboard, slugify
from bot.models import CarBrand, CarModel
from bot.states import CarModelForm

router = Router()


@router.callback_query(F.data == "admin:models")
async def models_pick_brand(cb: CallbackQuery):
    """Сначала выбор марки, затем список моделей."""
    await clear_stale_reply_keyboard(cb.message)
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        brands = (await db.execute(select(CarBrand).order_by(CarBrand.name))).scalars().all()

    lines = ["🔧 Модели авто", "", "Выберите марку:"]
    if not brands:
        lines.append("Сначала добавьте марку в разделе «🚗 Марки авто».")

    kb = InlineKeyboardBuilder()
    for b in brands:
        kb.row(InlineKeyboardButton(text=b.name, callback_data=f"admin:models:brand:{b.id}"))
    kb.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await cb.answer()


async def list_models_for_brand(cb: CallbackQuery, brand_id: int):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        brand = await db.get(CarBrand, brand_id)
        if not brand:
            await cb.answer("❌ Марка не найдена", show_alert=True)
            return
        models = (
            await db.execute(
                select(CarModel)
                .where(CarModel.brand_id == brand_id)
                .order_by(CarModel.name)
                .limit(50)
            )
        ).scalars().all()

    lines = [f"🔧 Модели — {brand.name}", ""]
    if not models:
        lines.append("Пока нет моделей для этой марки.")
    for m in models:
        lines.append(f"• {m.name} ({m.slug})")

    kb = InlineKeyboardBuilder()
    for m in models:
        kb.row(InlineKeyboardButton(text=m.name[:60], callback_data=f"admin:carmodel:{m.id}"))
    kb.row(InlineKeyboardButton(text="➕ Добавить", callback_data=f"admin:carmodel:add:{brand_id}"))
    kb.row(InlineKeyboardButton(text="🔙 К выбору марки", callback_data="admin:models"))
    await cb.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("admin:models:brand:"))
async def models_for_brand(cb: CallbackQuery):
    brand_id = int(cb.data.split(":")[-1])
    await list_models_for_brand(cb, brand_id)


@router.callback_query(F.data.startswith("admin:brand:models:"))
async def brand_models_list(cb: CallbackQuery):
    brand_id = int(cb.data.split(":")[-1])
    await list_models_for_brand(cb, brand_id)


@router.callback_query(F.data.startswith("admin:carmodel:add:"))
async def start_create_model(cb: CallbackQuery, state: FSMContext):
    preset_brand_id = int(cb.data.split(":")[-1])

    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        if not await db.get(CarBrand, preset_brand_id):
            await cb.answer("❌ Марка не найдена", show_alert=True)
            return

    await state.set_state(CarModelForm.name)
    await state.update_data(editing_model_id=None, brand_id=preset_brand_id)
    await cb.message.answer("Название модели:", reply_markup=form_keyboard())
    await cb.answer()


@router.callback_query(F.data.startswith("admin:carmodel:edit:"))
async def start_edit_model(cb: CallbackQuery, state: FSMContext):
    mid = int(cb.data.split(":")[-1])
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        model = await db.get(CarModel, mid)
        if not model:
            await cb.answer("❌ Модель не найдена", show_alert=True)
            return
    await state.set_state(CarModelForm.name)
    await state.update_data(
        editing_model_id=mid,
        name=model.name,
        slug=model.slug,
        brand_id=model.brand_id,
    )
    await cb.message.answer("Новое название (или `.` чтобы оставить):", reply_markup=form_keyboard(["."]))
    await cb.answer()


@router.message(CarModelForm.name)
async def model_name(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text == "🔙 Отмена":
        await state.clear()
        await msg.answer("Операция отменена.", reply_markup=remove_keyboard())
        return
    if text != ".":
        await state.update_data(name=text)
    await state.set_state(CarModelForm.slug)
    await msg.answer("Slug (или `auto`/`.`):", reply_markup=form_keyboard(["auto", "."]))


@router.message(CarModelForm.slug)
async def model_slug(msg: Message, state: FSMContext):
    data = await state.get_data()
    text = (msg.text or "").strip().lower()
    if text == "auto":
        await state.update_data(slug=slugify(data["name"]))
    elif text != ".":
        await state.update_data(slug=slugify(text))
    data = await state.get_data()
    if data.get("brand_id") is not None and not data.get("editing_model_id"):
        await model_save(msg, state)
        return
    await state.set_state(CarModelForm.brand_id)
    async with AsyncSessionLocal() as db:
        brands = (await db.execute(select(CarBrand).order_by(CarBrand.name))).scalars().all()
    if not brands:
        await msg.answer("Сначала создайте хотя бы одну марку.")
        await state.clear()
        return
    hints = [str(b.id) for b in brands[:8]]
    await msg.answer(
        "ID марки (число, или `.` чтобы оставить текущую):\n"
        + "\n".join(f"{b.id}: {b.name}" for b in brands),
        reply_markup=form_keyboard(hints + ["."], include_cancel=True),
    )


@router.message(CarModelForm.brand_id)
async def model_brand_id(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text != ".":
        try:
            brand_id = int(text)
        except ValueError:
            await msg.answer("Введите числовой ID марки или `.` чтобы оставить текущую.")
            return
        async with AsyncSessionLocal() as db:
            if not await db.get(CarBrand, brand_id):
                await msg.answer("Марка с таким ID не найдена.")
                return
        await state.update_data(brand_id=brand_id)
    await model_save(msg, state)


async def model_save(msg: Message, state: FSMContext):
    data = await state.get_data()
    payload = {
        "name": data["name"],
        "slug": data.get("slug") or slugify(data["name"]),
        "brand_id": data["brand_id"],
    }
    editing_id = data.get("editing_model_id")

    async with AsyncSessionLocal() as db:
        if not await db.get(CarBrand, payload["brand_id"]):
            await msg.answer("Марка не найдена.")
            return
        existing_slug = (
            await db.execute(select(CarModel).where(CarModel.slug == payload["slug"]))
        ).scalar_one_or_none()
        if existing_slug and existing_slug.id != editing_id:
            await msg.answer("Slug уже используется другой моделью.")
            return

        if editing_id:
            await db.execute(update(CarModel).where(CarModel.id == editing_id).values(**payload))
            await db.commit()
            result_text = "✅ Модель обновлена."
        else:
            db.add(CarModel(**payload))
            await db.commit()
            result_text = "✅ Модель создана."

    await state.clear()
    await msg.answer(result_text, reply_markup=remove_keyboard())


@router.callback_query(F.data.startswith("admin:carmodel:"))
async def model_actions_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return

    if len(parts) == 3 and parts[2].isdigit():
        mid = int(parts[2])
        model = (
            await db.execute(
                select(CarModel).options(selectinload(CarModel.brand)).where(CarModel.id == mid)
            )
        ).scalar_one_or_none()
        if not model:
            await cb.answer("❌ Модель не найдена", show_alert=True)
            return
        brand_name = model.brand.name if model.brand else "—"
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin:carmodel:edit:{mid}"))
        kb.row(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin:carmodel:del:{mid}"))
        kb.row(
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data=f"admin:models:brand:{model.brand_id}",
            )
        )
        await cb.message.edit_text(
            f"🔧 {model.name}\nSlug: {model.slug}\nМарка: {brand_name}",
            reply_markup=kb.as_markup(),
        )
        await cb.answer()
        return

    if len(parts) == 4 and parts[2] == "del" and parts[3].isdigit():
        mid = int(parts[3])
        model = await db.get(CarModel, mid)
        brand_id = model.brand_id if model else None
        await db.execute(delete(CarModel).where(CarModel.id == mid))
        await db.commit()
        await cb.answer("🗑 Модель удалена")
        if brand_id:
            await list_models_for_brand(cb, brand_id)
        else:
            await models_pick_brand(cb)
        return

    await cb.answer()
