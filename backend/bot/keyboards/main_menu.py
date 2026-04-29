from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"))
    b.row(InlineKeyboardButton(text="📁 Категории", callback_data="admin:categories"))
    b.row(InlineKeyboardButton(text="🛍️ Продукты", callback_data="admin:products"))
    b.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:refresh"))
    return b.as_markup()