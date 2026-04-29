from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from bot.keyboards.main_menu import get_main_menu
from bot.config import settings
from bot.database import AsyncSessionLocal
from bot.models import User
from sqlalchemy import select

router = Router()

async def is_admin(user_id: int) -> bool:
    if user_id in settings.admin_ids_list: return True
    async with AsyncSessionLocal() as db:
        u = await db.execute(select(User).where(User.telegram_id == user_id))
        user = u.scalars().first()
        return user and user.role == "ADMIN"

@router.message(CommandStart())
async def cmd_start(msg: Message):
    if not await is_admin(msg.from_user.id):
        await msg.answer("❌ Доступ запрещен. Только для администраторов.")
        return
    await msg.answer("🛠️ **Админ-панель СинтезКар**\nВыберите раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")

@router.callback_query(F.data == "admin:menu" | F.data == "admin:refresh")
async def show_menu(cb: CallbackQuery):
    await cb.message.edit_text("🛠️ **Админ-панель СинтезКар**\nВыберите раздел:", reply_markup=get_main_menu(), parse_mode="Markdown")
    await cb.answer()