from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, update, func
from bot.database import AsyncSessionLocal
from bot.models import User, UserRole
from bot.keyboards.users_kb import users_list, user_actions

router = Router()

@router.callback_query(F.data == "admin:users")
async def list_users(cb: CallbackQuery, page: int = 1):
    async with AsyncSessionLocal() as db:
        total = await db.scalar(select(func.count(User.id)))
        users = (await db.execute(select(User).order_by(User.last_seen.desc()).offset((page-1)*10).limit(10))).scalars().all()
    txt = f"👥 **Пользователи** (стр. {page})\n" + "\n".join(f"{i}. `{u.telegram_id}` — {u.username or 'Нет'} ({u.role})" for i, u in enumerate(users, (page-1)*10+1))
    await cb.message.edit_text(txt, reply_markup=users_list(users, page), parse_mode="Markdown")
    await cb.answer()

@router.callback_query(F.data.startswith("admin:user:"))
async def user_cb(cb: CallbackQuery):
    parts = cb.data.split(":")
    if len(parts) == 3:
        async with AsyncSessionLocal() as db:
            u = await db.get(User, int(parts[2]))
        if not u: return await cb.answer("❌ Не найден", show_alert=True)
        txt = f"👤 {u.first_name} (@{u.username or '—'})\nID: `{u.telegram_id}`\nРоль: `{u.role}`\nПоследний вход: `{u.last_seen}`"
        await cb.message.edit_text(txt, reply_markup=user_actions(u.id, u.role.value), parse_mode="Markdown")
    elif len(parts) == 5 and parts[2] == "role":
        new_role, uid = parts[3], int(parts[4])
        async with AsyncSessionLocal() as db:
            await db.execute(update(User).where(User.id == uid).values(role=UserRole(new_role)))
            await db.commit()
        await cb.answer("✅ Роль изменена")
        await list_users(cb, page=1)
    await cb.answer()

@router.callback_query(F.data.startswith("admin:users:p:"))
async def users_page(cb: CallbackQuery):
    await list_users(cb, int(cb.data.split(":")[-1]))