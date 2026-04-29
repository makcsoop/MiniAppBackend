import asyncio
import logging
from aiogram import Bot, Dispatcher
from bot.config import settings
from bot.handlers import start_menu, users, categories, products

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

dp.include_router(start_menu.router)
dp.include_router(users.router)
dp.include_router(categories.router)
dp.include_router(products.router)

@dp.callback_query()
async def unhandled(cb):
    await cb.answer("⚠️ В разработке", show_alert=True)

async def main():
    me = await bot.get_me()
    logging.info(f"🤖 Bot @{me.username} started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())