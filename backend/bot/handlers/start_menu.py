# bot/handlers/start_menu.py
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import settings
from bot.database import AsyncSessionLocal
from bot.handlers.common import (
    ADMIN_MENU_TEXT,
    admin_main_menu,
    clear_stale_reply_keyboard,
    ensure_admin,
    is_plausible_phone,
    normalize_phone,
    remove_keyboard,
    request_contact_keyboard,
    upsert_user_from_telegram,
)
from bot.states import OnboardingForm

router = Router()


def _user_welcome_text() -> str:
    lines = [
        "Привет! Это бот сервиса Mini App в Telegram.",
        "",
        "Поделитесь номером телефона — так мы привяжем ваш аккаунт в базе (стандартный сценарий для Mini App).",
        "Данные используются для связи с вами по заказам и уведомлениям.",
        "",
        "После сохранения номера откройте приложение через кнопку Mini App у этого бота.",
    ]
    url = (settings.MINI_APP_URL or "").strip()
    if url:
        lines.extend(["", f"Ссылка на Mini App: {url}"])
    return "\n".join(lines)


def _user_registered_text() -> str:
    lines = [
        "Номер телефона уже сохранён в вашем профиле.",
        "Можете открыть Mini App.",
    ]
    url = (settings.MINI_APP_URL or "").strip()
    if url:
        lines.extend(["", url])
    return "\n".join(lines)


def _user_thanks_text() -> str:
    lines = [
        "Спасибо! Номер телефона сохранён.",
        "Теперь можно пользоваться Mini App.",
    ]
    url = (settings.MINI_APP_URL or "").strip()
    if url:
        lines.extend(["", url])
    return "\n".join(lines)


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    async with AsyncSessionLocal() as db:
        if await ensure_admin(msg.from_user.id, db):
            await clear_stale_reply_keyboard(msg)
            await msg.answer(ADMIN_MENU_TEXT, reply_markup=admin_main_menu())
            return

        user = await upsert_user_from_telegram(db, msg.from_user)
        if user.phone_number and str(user.phone_number).strip():
            await db.commit()
            await clear_stale_reply_keyboard(msg)
            await msg.answer(_user_registered_text())
            return

        await db.commit()

    await state.set_state(OnboardingForm.waiting_phone)
    await clear_stale_reply_keyboard(msg)
    await msg.answer(_user_welcome_text(), reply_markup=request_contact_keyboard())


@router.callback_query(F.data.in_(["admin:menu", "admin:refresh"]))
async def show_menu(cb: CallbackQuery):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
    await clear_stale_reply_keyboard(cb.message)
    await cb.message.edit_text(ADMIN_MENU_TEXT, reply_markup=admin_main_menu())
    await cb.answer()


@router.message(F.contact)
async def handle_shared_contact(msg: Message, state: FSMContext):
    """Сохранение телефона из контакта (onboarding или повторная отправка)."""
    contact = msg.contact
    if not contact or contact.user_id != msg.from_user.id:
        await msg.answer("Поделитесь именно своим номером — нажмите кнопку «Поделиться номером».")
        return

    raw = (contact.phone_number or "").strip()
    if not raw:
        await msg.answer("Не удалось прочитать номер. Попробуйте ещё раз.")
        return

    phone = normalize_phone(raw)
    async with AsyncSessionLocal() as db:
        if await ensure_admin(msg.from_user.id, db):
            await state.clear()
            return
        user = await upsert_user_from_telegram(db, msg.from_user)
        user.phone_number = phone
        await db.commit()

    await state.clear()
    await msg.answer(_user_thanks_text(), reply_markup=remove_keyboard())


@router.message(OnboardingForm.waiting_phone, F.text)
async def onboarding_manual_phone(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if text == "🔙 Отмена":
        await state.clear()
        await msg.answer("Без номера часть функций Mini App может быть недоступна.", reply_markup=remove_keyboard())
        return

    if not is_plausible_phone(text):
        await msg.answer(
            "Введите номер в формате +79001234567 или нажмите «Поделиться номером».",
            reply_markup=request_contact_keyboard(),
        )
        return

    phone = normalize_phone(text)
    async with AsyncSessionLocal() as db:
        if await ensure_admin(msg.from_user.id, db):
            await state.clear()
            return
        user = await upsert_user_from_telegram(db, msg.from_user)
        user.phone_number = phone
        await db.commit()

    await state.clear()
    await msg.answer(_user_thanks_text(), reply_markup=remove_keyboard())
