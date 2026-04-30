# bot/handlers/products.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from bot.database import AsyncSessionLocal
from bot.models import Product, ProductStatus
from bot.keyboards.products_kb import products_list, product_actions

router = Router()

@router.callback_query(F.data == "admin:products")
async def list_products(cb: CallbackQuery):
    """Показать список продуктов (последние 20)"""
    async with AsyncSessionLocal() as db:
        prods = (await db.execute(
            select(Product).order_by(Product.created_at.desc()).limit(20)
        )).scalars().all()
    
    if not prods:
        text = "🛍️ **Продукты**\n\nПока нет продуктов."
    else:
        text = "🛍️ **Продукты** (последние 20)\n\n"
        for p in prods:
            status = "✅" if p.status == "ACTIVE" else "⏸️"
            cat = p.category.name if p.category else "Без категории"
            text += f"{status} `{p.slug}` — {p.title} ({p.price} {p.currency})\n"
    
    kb = products_list(prods) if prods else get_main_menu()
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("admin:prod:"))
async def product_actions_cb(cb: CallbackQuery):
    """Действия с продуктом: смена статуса"""
    parts = cb.data.split(":")
    
    # admin:prod:{id} — показать инфо
    if len(parts) == 3:
        pid = int(parts[2])
        async with AsyncSessionLocal() as db:
            p = await db.get(Product, pid)
        if not p:
            await cb.answer("❌ Продукт не найден", show_alert=True)
            return
        cat_name = p.category.name if p.category else "Без категории"
        text = (
            f"🛍️ **Продукт**\n\n"
            f"• Название: {p.title}\n"
            f"• Slug: `{p.slug}`\n"
            f"• Цена: `{p.price} {p.currency}`\n"
            f"• Статус: `{p.status}`\n"
            f"• Категория: {cat_name}\n"
            f"• В избранном: {'✅' if p.is_featured else '❌'}"
        )
        await cb.message.edit_text(
            text,
            reply_markup=product_actions(pid, p.status.value),
            parse_mode="Markdown"
        )
        await cb.answer()
    
    # admin:prod:status:{id}:{NEW_STATUS} — изменить статус
    elif len(parts) == 5 and parts[2] == "status":
        pid, new_status = int(parts[3]), parts[4]
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Product).where(Product.id == pid).values(
                    status=ProductStatus(new_status)
                )
            )
            await db.commit()
        await cb.answer("✅ Статус изменен")
        await list_products(cb)
    
    await cb.answer()