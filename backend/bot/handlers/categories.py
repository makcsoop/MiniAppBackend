from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from bot.database import AsyncSessionLocal
from bot.models import Category
from bot.keyboards.categories_kb import categories_list, category_actions

router = Router()

@router.callback_query(F.data == "admin:categories")
async def list_cats(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        cats = (await db.execute(select(Category).order_by(Category.sort_order))).scalars().all()
    txt = "📁 **Категории**\n" + "\n".join(f"{'✅' if c.is_active else '❌'} `{c.slug}` — {c.name}" for c in cats)
    await cb.message.edit_text(txt, reply_markup=categories_list(cats), parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("admin:cat:"))
async def cat_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) == 3:
        async with AsyncSessionLocal() as db:
            c = await db.get(Category, int(parts[2]))
        if not c: return await cb.answer("❌", show_alert=True)
        txt = f"📁 {c.name}\nSlug: `{c.slug}`\nАктивна: {'✅' if c.is_active else '❌'}"
        await cb.message.edit_text(txt, reply_markup=category_actions(c.id, c.is_active), parse_mode="Markdown")
    elif len(parts) == 5 and parts[2] == "toggle":
        uid, action = int(parts[3]), parts[4]
        async with AsyncSessionLocal() as db:
            await db.execute(update(Category).where(Category.id == uid).values(is_active=(action == "activate")))
            await db.commit()
        await cb.answer("✅ Обновлено")
        await list_cats(cb)
    await cb.answer()