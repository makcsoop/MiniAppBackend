from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func

from bot.database import AsyncSessionLocal
from bot.handlers.common import ensure_admin
from bot.models import User, Booking, Category, Product, ProductStatus

router = Router()


@router.callback_query(F.data == "admin:stats")
async def show_stats(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return

        users_total = int(await db.scalar(select(func.count(User.id))) or 0)
        users_blocked = int(await db.scalar(select(func.count(User.id)).where(User.is_blocked.is_(True))) or 0)
        users_admins = int(await db.scalar(select(func.count(User.id)).where(User.role == "ADMIN")) or 0)
        bookings_total = int(await db.scalar(select(func.count(Booking.id))) or 0)
        categories_total = int(await db.scalar(select(func.count(Category.id))) or 0)
        categories_active = int(await db.scalar(select(func.count(Category.id)).where(Category.is_active.is_(True))) or 0)
        products_total = int(await db.scalar(select(func.count(Product.id))) or 0)
        products_active = int(
            await db.scalar(select(func.count(Product.id)).where(Product.status == ProductStatus.ACTIVE)) or 0
        )

    text = (
        "📊 Общая статистика\n\n"
        f"Пользователи: {users_total}\n"
        f"Админы: {users_admins}\n"
        f"Заблокированные: {users_blocked}\n\n"
        f"Бронирования/покупки: {bookings_total}\n\n"
        f"Категории: {categories_total} (активных: {categories_active})\n"
        f"Услуги/товары: {products_total} (активных: {products_active})"
    )

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    await cb.message.edit_text(text, reply_markup=b.as_markup())
    await cb.answer()
