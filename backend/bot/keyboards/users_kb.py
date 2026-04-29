from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def users_list(users: list, page: int = 1) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for u in users:
        role = "👑" if u.role == "ADMIN" else "👤"
        name = u.username or f"ID:{u.telegram_id}"
        b.row(InlineKeyboardButton(text=f"{role} {name}", callback_data=f"admin:user:{u.id}"))
    if page > 1: b.row(InlineKeyboardButton(text="⬅️", callback_data=f"admin:users:p:{page-1}"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    if len(users) == 10: b.row(InlineKeyboardButton(text="➡️", callback_data=f"admin:users:p:{page+1}"))
    return b.as_markup()

def user_actions(user_id: int, role: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    new_role = "USER" if role == "ADMIN" else "ADMIN"
    txt = "👤 В пользователи" if role == "ADMIN" else "👑 В админы"
    b.row(InlineKeyboardButton(text=txt, callback_data=f"admin:user:role:{new_role}:{user_id}"))
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:users"))
    return b.as_markup()