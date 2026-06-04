from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import TrainerProfile, User
from src.utils.db import SessionLocal

router = Router()

@router.message(F.text == "🔍 Найти тренера")
async def show_catalog(message: types.Message):
    async with SessionLocal() as session:
        query = select(TrainerProfile, User).join(User, TrainerProfile.user_id == User.id)
        result = await session.execute(query)
        trainers = result.all()

        if not trainers:
            await message.answer("К сожалению, тренеров пока нет.")
            return

        for trainer_profile, user in trainers:
            text = (
                f"👤 {user.full_name}\n"
                f"📍 Город: {trainer_profile.city}\n"
                f"💪 Опыт: {trainer_profile.experience}\n"
                f"💰 Цена: {trainer_profile.price_per_session}₽\n"
                f"⭐ Рейтинг: {trainer_profile.rating}\n"
                f"📝 Формат: {trainer_profile.work_format.value}"
            )
            if trainer_profile.photo_url:
                await message.answer_photo(trainer_profile.photo_url, caption=text)
            else:
                await message.answer(text)
