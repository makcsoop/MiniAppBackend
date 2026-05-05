from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, func

from bot.database import AsyncSessionLocal
from bot.handlers.common import PAGE_SIZE, clean_text, ensure_admin, format_dt, purchases_count_for_user
from bot.models import User, UserRole

router = Router()


@router.callback_query(F.data == "admin:users")
async def list_users(cb: CallbackQuery, page: int = 1):
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return
        total = await db.scalar(select(func.count(User.id)))
        users = (
            await db.execute(
                select(User)
                .order_by(User.last_seen.desc())
                .offset((page - 1) * PAGE_SIZE)
                .limit(PAGE_SIZE)
            )
        ).scalars().all()

    lines = [f"👥 Пользователи (стр. {page}, всего {total})", ""]
    if not users:
        lines.append("Пока нет пользователей.")
    for idx, user in enumerate(users, start=((page - 1) * PAGE_SIZE) + 1):
        role_icon = "👑" if user.role == UserRole.ADMIN else "👤"
        blocked_icon = "🚫" if getattr(user, "is_blocked", False) else "✅"
        lines.append(f"{idx}. {role_icon}{blocked_icon} {clean_text(user.username)} (tg:{user.telegram_id})")

    b = InlineKeyboardBuilder()
    for user in users:
        role_icon = "👑" if user.role == UserRole.ADMIN else "👤"
        blocked_icon = "🚫" if getattr(user, "is_blocked", False) else "✅"
        b.row(
            InlineKeyboardButton(
                text=f"{role_icon}{blocked_icon} {clean_text(user.username or user.first_name)}",
                callback_data=f"admin:user:{user.id}",
            )
        )
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin:users:p:{page-1}"))
    if len(users) == PAGE_SIZE:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin:users:p:{page+1}"))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="🔙 Меню", callback_data="admin:menu"))
    await cb.message.edit_text("\n".join(lines), reply_markup=b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("admin:user:"))
async def user_actions_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    async with AsyncSessionLocal() as db:
        if not await ensure_admin(cb.from_user.id, db):
            await cb.answer("❌ Недостаточно прав", show_alert=True)
            return

        if len(parts) == 3:
            uid = int(parts[2])
            u = await db.get(User, uid)
            if not u:
                await cb.answer("❌ Пользователь не найден", show_alert=True)
                return

            purchases = await purchases_count_for_user(db, u.id)
            text = (
                "👤 Карточка пользователя\n\n"
                f"ID: {u.telegram_id}\n"
                f"Username: @{clean_text(u.username)}\n"
                f"Имя: {clean_text(u.first_name)} {clean_text(u.last_name)}\n"
                f"Роль: {u.role.value}\n"
                f"Premium: {'Да' if u.is_premium else 'Нет'}\n"
                f"Покупок/броней: {purchases}\n"
                f"Последнее посещение: {format_dt(u.last_seen)}\n"
                f"Дата регистрации: {format_dt(u.created_at)}\n"
                f"Блокировка: {'Да' if getattr(u, 'is_blocked', False) else 'Нет'}"
            )

            b = InlineKeyboardBuilder()
            new_role = UserRole.ADMIN if u.role == UserRole.USER else UserRole.USER
            b.row(
                InlineKeyboardButton(
                    text="👑 Сделать админом" if new_role == UserRole.ADMIN else "👤 Сделать пользователем",
                    callback_data=f"admin:user:role:{new_role.value}:{u.id}",
                )
            )
            block_text = "🚫 Заблокировать" if not getattr(u, "is_blocked", False) else "✅ Разблокировать"
            block_action = "block" if not getattr(u, "is_blocked", False) else "unblock"
            b.row(InlineKeyboardButton(text=block_text, callback_data=f"admin:user:block:{block_action}:{u.id}"))
            b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:users"))
            await cb.message.edit_text(text, reply_markup=b.as_markup())
            await cb.answer()
            return

        if len(parts) == 5 and parts[2] == "role":
            new_role, uid = parts[3], int(parts[4])
            await db.execute(update(User).where(User.id == uid).values(role=UserRole(new_role)))
            await db.commit()
            await cb.answer(f"✅ Роль изменена на {new_role}")
            await list_users(cb, page=1)
            return

        if len(parts) == 5 and parts[2] == "block":
            action, uid = parts[3], int(parts[4])
            updates = {"is_blocked": action == "block"}
            if action == "block":
                updates["blocked_reason"] = "Заблокирован из админ-бота"
                updates["blocked_at"] = func.now()
            else:
                updates["blocked_reason"] = None
                updates["blocked_at"] = None
            await db.execute(update(User).where(User.id == uid).values(**updates))
            await db.commit()
            await cb.answer("✅ Статус блокировки обновлен")
            updated = await db.get(User, uid)
            b = InlineKeyboardBuilder()
            b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:users"))
            await cb.message.edit_text(
                f"Пользователь @{clean_text(updated.username)} {'заблокирован' if updated.is_blocked else 'разблокирован'}.",
                reply_markup=b.as_markup(),
            )
            return

    await cb.answer()


@router.callback_query(F.data.startswith("admin:users:p:"))
async def users_page(cb: CallbackQuery):
    page = int(cb.data.split(":")[-1])
    await list_users(cb, page)