# bot/handlers/users.py
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, update, func
from bot.database import AsyncSessionLocal
from bot.models import User, UserRole
from bot.keyboards.users_kb import users_list, user_actions

router = Router()

@router.callback_query(F.data == "admin:users")
async def list_users(cb: CallbackQuery, page: int = 1):
    """Показать список пользователей с пагинацией"""
    async with AsyncSessionLocal() as db:
        total = await db.scalar(select(func.count(User.id)))
        users = (await db.execute(
            select(User).order_by(User.last_seen.desc()).offset((page-1)*10).limit(10)
        )).scalars().all()
    
    if not users:
        text = "👥 **Пользователи**\n\nПока нет пользователей."
    else:
        text = f"👥 **Пользователи** (стр. {page}, всего {total})\n\n"
        for i, u in enumerate(users, start=(page-1)*10+1):
            name = u.username or f"ID:{u.telegram_id}"
            role = "👑" if u.role == "ADMIN" else "👤"
            text += f"{i}. {role} `{u.telegram_id}` — {name}\n"
    
    kb = users_list(users, page) if users else get_main_menu()
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("admin:user:"))
async def user_actions_cb(cb: CallbackQuery):
    """Действия с пользователем: просмотр, смена роли"""
    parts = cb.data.split(":")
    
    # admin:user:{id} — показать инфо
    if len(parts) == 3:
        uid = int(parts[2])
        async with AsyncSessionLocal() as db:
            u = await db.get(User, uid)
        if not u:
            await cb.answer("❌ Пользователь не найден", show_alert=True)
            return
        text = (
            f"👤 **Пользователь**\n\n"
            f"• Telegram ID: `{u.telegram_id}`\n"
            f"• Username: @{u.username or '—'}\n"
            f"• Имя: {u.first_name or '—'}\n"
            f"• Роль: `{u.role}`\n"
            f"• Premium: {'✅' if u.is_premium else '❌'}\n"
            f"• Последний вход: `{u.last_seen}`"
        )
        await cb.message.edit_text(
            text,
            reply_markup=user_actions(uid, u.role.value),
            parse_mode="Markdown"
        )
        await cb.answer()
    
    # admin:user:role:{NEW_ROLE}:{user_id} — изменить роль
    elif len(parts) == 5 and parts[2] == "role":
        new_role, uid = parts[3], int(parts[4])
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(User).where(User.id == uid).values(role=UserRole(new_role))
            )
            await db.commit()
        await cb.answer(f"✅ Роль изменена на {new_role}")
        await list_users(cb, page=1)
    
    await cb.answer()

@router.callback_query(F.data.startswith("admin:users:p:"))
async def users_page(cb: CallbackQuery):
    """Пагинация списка пользователей"""
    page = int(cb.data.split(":")[-1])
    await list_users(cb, page)