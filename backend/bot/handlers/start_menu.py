# bot/handlers/start_menu.py
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.database import AsyncSessionLocal
from bot.handlers.common import ADMIN_MENU_TEXT, admin_main_menu, ensure_admin

router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(msg.from_user.id, db):
            await msg.answer("❌ Доступ запрещен. Только для администраторов.")
            return
    await msg.answer(ADMIN_MENU_TEXT, reply_markup=admin_main_menu())


@router.callback_query(F.data.in_(["admin:menu", "admin:refresh"]))
async def show_menu(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
    await cb.message.edit_text(ADMIN_MENU_TEXT, reply_markup=admin_main_menu())
    await cb.answer()