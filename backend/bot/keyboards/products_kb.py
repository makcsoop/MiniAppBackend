from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def products_list(prods: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in prods:
        status = "✅" if p.status == "ACTIVE" else "⏸️"
        b.row(InlineKeyboardButton(text=f"{status} {p.title} ({p.price} {p.currency})", callback_data=f"admin:prod:{p.id}"))
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    return b.as_markup()

def product_actions(prod_id: int, status: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    action = "ARCHIVED" if status == "ACTIVE" else "ACTIVE"
    txt = "📦 Скрыть" if status == "ACTIVE" else "🌍 Показать"
    b.row(InlineKeyboardButton(text=txt, callback_data=f"admin:prod:status:{prod_id}:{action}"))
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:products"))
    return b.as_markup()