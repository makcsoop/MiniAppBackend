import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import settings
from bot.database import AsyncSessionLocal
from bot.handlers import brands, car_models, categories, products, start_menu, stats, users
from bot.handlers.common import admin_main_menu, ensure_admin, remove_keyboard

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
logger = logging.getLogger(__name__)


bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

dp.include_router(start_menu.router)
dp.include_router(users.router)
dp.include_router(categories.router)
dp.include_router(products.router)
dp.include_router(brands.router)
dp.include_router(car_models.router)
dp.include_router(stats.router)


@dp.message(F.text == "🔙 Отмена")
async def cancel_any_form(msg: Message, state: FSMContext):
    current_state = await state.get_state()
    if not current_state:
        return
    await state.clear()
    async with AsyncSessionLocal() as db:
        is_admin_user = await ensure_admin(msg.from_user.id, db)
    if is_admin_user:
        await msg.answer("Операция отменена.", reply_markup=admin_main_menu())
    else:
        await msg.answer("Операция отменена.", reply_markup=remove_keyboard())


async def main():
    me = await bot.get_me()
    logger.info("Bot @%s started", me.username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())