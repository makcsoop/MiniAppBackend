# bot/handlers/categories.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from bot.database import AsyncSessionLocal
from bot.models import Category
from bot.keyboards.categories_kb import categories_list, category_actions

router = Router()

@router.callback_query(F.data == "admin:categories")
async def list_categories(cb: CallbackQuery):
    """Показать список категорий"""
    async with AsyncSessionLocal() as db:
        cats = (await db.execute(
            select(Category).order_by(Category.sort_order, Category.name)
        )).scalars().all()
    
    if not cats:
        text = "📁 **Категории**\n\nПока нет категорий."
    else:
        text = "📁 **Категории**\n\n"
        for c in cats:
            status = "✅" if c.is_active else "❌"
            text += f"{status} `{c.slug}` — {c.name}\n"
    
    kb = categories_list(cats) if cats else get_main_menu()
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("admin:cat:"))
async def category_actions_cb(cb: CallbackQuery):
    """Действия с категорией: активация/деактивация"""
    parts = cb.data.split(":")
    
    # admin:cat:{id} — показать инфо
    if len(parts) == 3:
        cid = int(parts[2])
        async with AsyncSessionLocal() as db:
            c = await db.get(Category, cid)
        if not c:
            await cb.answer("❌ Категория не найдена", show_alert=True)
            return
        text = (
            f"📁 **Категория**\n\n"
            f"• Название: {c.name}\n"
            f"• Slug: `{c.slug}`\n"
            f"• Описание: {c.description or '—'}\n"
            f"• Активна: {'✅' if c.is_active else '❌'}\n"
            f"• Порядок: `{c.sort_order}`"
        )
        await cb.message.edit_text(
            text,
            reply_markup=category_actions(cid, c.is_active),
            parse_mode="Markdown"
        )
        await cb.answer()
    
    # admin:cat:toggle:{id}:{action} — активировать/деактивировать
    elif len(parts) == 5 and parts[2] == "toggle":
        cid, action = int(parts[3]), parts[4]
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Category).where(Category.id == cid).values(
                    is_active=(action == "activate")
                )
            )
            await db.commit()
        await cb.answer("✅ Изменения сохранены")
        await list_categories(cb)
    
    await cb.answer()