from __future__ import annotations

from datetime import datetime
import re
from typing import Optional

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.models import User

ADMIN_MENU_TEXT = "🛠️ Админ-панель MiniApp\nВыберите раздел:"
PAGE_SIZE = 10


def admin_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"))
    builder.row(InlineKeyboardButton(text="📁 Категории", callback_data="admin:categories"))
    builder.row(InlineKeyboardButton(text="🛍️ Услуги", callback_data="admin:products"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"))
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="admin:refresh"))
    return builder.as_markup()


def form_keyboard(*rows: list[str], include_cancel: bool = True) -> ReplyKeyboardMarkup:
    keyboard_rows = [[KeyboardButton(text=text) for text in row] for row in rows]
    if include_cancel:
        keyboard_rows.append([KeyboardButton(text="🔙 Отмена")])
    return ReplyKeyboardMarkup(
        keyboard=keyboard_rows,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Выберите вариант или введите значение",
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return form_keyboard(include_cancel=True)


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


async def is_admin(user_id: int, db: AsyncSession) -> bool:
    if user_id in settings.admin_ids_list:
        return True
    result = await db.execute(select(User.role).where(User.telegram_id == user_id))
    role = result.scalar_one_or_none()
    return role == "ADMIN"


def clean_text(value: Optional[str]) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    return text if text else "—"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\-\s_]", "", value.strip().lower())
    slug = slug.replace("_", "-")
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


def format_dt(value: Optional[datetime]) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M")


async def ensure_admin(user_id: int, db: AsyncSession) -> bool:
    return await is_admin(user_id, db)


async def purchases_count_for_user(db: AsyncSession, user_id: int) -> int:
    from bot.models import Booking

    result = await db.execute(select(func.count(Booking.id)).where(Booking.user_id == user_id))
    return int(result.scalar() or 0)
