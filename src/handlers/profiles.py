from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import User, TrainerProfile, ClientProfile, UserRole
from src.utils.db import SessionLocal

router = Router()

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start")
            return

        if user.role == UserRole.TRAINER:
            query = select(TrainerProfile).where(TrainerProfile.user_id == user.id)
            result = await session.execute(query)
            profile = result.scalar_one_or_none()
            if profile:
                text = (
                    f"👤 Профиль тренера: {user.full_name}\n"
                    f"📍 Город: {profile.city}\n"
                    f"💪 Опыт: {profile.experience}\n"
                    f"💰 Цена: {profile.price_per_session}₽\n"
                    f"⭐ Рейтинг: {profile.rating}\n"
                    f"📝 Формат: {profile.work_format.value}"
                )
                await message.answer(text)
            else:
                await message.answer("Профиль тренера не найден. Попробуйте перерегистрироваться.")

        elif user.role == UserRole.CLIENT:
            query = select(ClientProfile).where(ClientProfile.user_id == user.id)
            result = await session.execute(query)
            profile = result.scalar_one_or_none()
            if profile:
                text = (
                    f"👤 Профиль клиента: {user.full_name}\n"
                    f"📍 Город: {profile.city or 'Не указан'}"
                )
                await message.answer(text)
            else:
                await message.answer("Профиль клиента не найден.")
