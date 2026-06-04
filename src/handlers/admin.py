from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import User, TrainerProfile, UserRole
from src.utils.db import SessionLocal

router = Router()

# In a real bot, we'd check against a list of admin user IDs
ADMIN_IDS = [] # Add admin IDs here

@router.message(F.text == "/admin")
async def admin_panel(message: types.Message):
    # Simple check for now
    if message.from_user.id not in ADMIN_IDS:
        # await message.answer("У вас нет прав доступа к этой команде.")
        # return
        pass # Allow for now for development

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Верификация тренеров", callback_data="admin_verify_trainers")],
            [types.InlineKeyboardButton(text="Управление специализациями", callback_data="admin_manage_specs")]
        ]
    )
    await message.answer("Панель администратора:", reply_markup=kb)

@router.callback_query(F.data == "admin_verify_trainers")
async def list_unverified_trainers(callback: types.CallbackQuery):
    async with SessionLocal() as session:
        # For now, let's just list all trainers.
        # In the future, we could add an 'is_verified' field to TrainerProfile.
        query = select(TrainerProfile, User).join(User, TrainerProfile.user_id == User.id)
        result = await session.execute(query)
        trainers = result.all()

        if not trainers:
            await callback.message.answer("Список тренеров пуст.")
            return

        for profile, user in trainers:
            text = f"Тренер: {user.full_name}\nГород: {profile.city}\nID: {user.id}"
            kb = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="✅ Верифицировать", callback_data=f"verify_{user.id}")],
                    [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")]
                ]
            )
            await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("verify_"))
async def verify_trainer(callback: types.CallbackQuery):
    trainer_id = callback.data.split("_")[1]
    await callback.message.edit_text(f"Тренер {trainer_id} верифицирован (Mock).")
    await callback.answer()
