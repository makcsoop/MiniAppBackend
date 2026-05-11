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
from bot.models import User, UserRole

ADMIN_MENU_TEXT = "🛠️ Админ-панель MiniApp\nВыберите раздел:"
PAGE_SIZE = 10

PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{10,20}$")


def request_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Нажмите кнопку или введите номер вручную",
    )


async def upsert_user_from_telegram(db: AsyncSession, tg_user) -> User:
    """Создаёт или обновляет пользователя по данным Telegram (для бота и Mini App)."""
    result = await db.execute(select(User).where(User.telegram_id == tg_user.id))
    user = result.scalar_one_or_none()
    if user:
        user.username = tg_user.username or user.username
        user.first_name = tg_user.first_name or user.first_name
        user.last_name = tg_user.last_name or user.last_name
        user.language_code = getattr(tg_user, "language_code", None) or user.language_code
        user.is_premium = bool(getattr(tg_user, "is_premium", False) or user.is_premium)
        return user
    user = User(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        language_code=getattr(tg_user, "language_code", None),
        is_premium=bool(getattr(tg_user, "is_premium", False)),
        role=UserRole.USER,
    )
    db.add(user)
    return user


def normalize_phone(raw: str) -> str:
    return re.sub(r"[\s\-()]", "", (raw or "").strip())


def is_plausible_phone(raw: str) -> bool:
    if not raw or not PHONE_RE.match(raw.strip()):
        return False
    digits = re.sub(r"\D", "", raw)
    return 10 <= len(digits) <= 15


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


async def clear_stale_reply_keyboard(message) -> None:
    """
    Reply keyboard persists across inline edits.
    Send-and-delete service message to force keyboard removal.
    """
    service_msg = await message.answer(".", reply_markup=ReplyKeyboardRemove())
    await service_msg.delete()


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
