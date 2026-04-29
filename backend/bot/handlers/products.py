from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from bot.database import AsyncSessionLocal
from bot.models import Product, ProductStatus
from bot.keyboards.products_kb import products_list, product_actions

router = Router()

@router.callback_query(F.data == "admin:products")
async def list_prods(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        prods = (await db.execute(select(Product).order_by(Product.created_at.desc()).limit(20))).scalars().all()
    txt = "🛍️ **Продукты** (последние 20)\n" + "\n".join(f"{'✅' if p.status=='ACTIVE' else '⏸️'} {p.title} ({p.price} {p.currency})" for p in prods)
    await cb.message.edit_text(txt, reply_markup=products_list(prods), parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("admin:prod:"))
async def prod_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) == 3:
        async with AsyncSessionLocal() as db:
            p = await db.get(Product, int(parts[2]))
        if not p: return await cb.answer("❌", show_alert=True)
        cat_name = p.category.name if p.category else "Без категории"
        txt = f"🛍️ {p.title}\nЦена: `{p.price} {p.currency}`\nСтатус: `{p.status}`\nКатегория: {cat_name}"
        await cb.message.edit_text(txt, reply_markup=product_actions(p.id, p.status.value), parse_mode="Markdown")
    elif len(parts) == 5 and parts[2] == "status":
        pid, new_status = int(parts[3]), parts[4]
        async with AsyncSessionLocal() as db:
            await db.execute(update(Product).where(Product.id == pid).values(status=ProductStatus(new_status)))
            await db.commit()
        await cb.answer("✅ Статус изменен")
        await list_prods(cb)
    await cb.answer()