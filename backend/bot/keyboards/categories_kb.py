from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def categories_list(cats: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in cats:
        status = "✅" if c.is_active else "❌"
        b.row(InlineKeyboardButton(text=f"{status} {c.name}", callback_data=f"admin:cat:{c.id}"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    return b.as_markup()

def category_actions(cat_id: int, active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    action = "deactivate" if active else "activate"
    txt = "🔴 Деактивировать" if active else "🟢 Активировать"
    b.row(InlineKeyboardButton(text=txt, callback_data=f"admin:cat:toggle:{cat_id}:{action}"))
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:categories"))
    return b.as_markup()