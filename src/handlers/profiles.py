from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import User, TrainerProfile, ClientProfile, UserRole
from src.utils.db import SessionLocal

router = Router()

@router.message(F.text.in_(["👤 Мой профиль", "👤 Профиль"]))
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

@router.message(F.text == "📆 Расписание")
async def show_schedule(message: types.Message):
    await message.answer("Ваше расписание на сегодня пусто. Интеграция с Google Calendar будет доступна в следующем обновлении.")

@router.message(F.text == "👥 Мои клиенты")
async def show_clients(message: types.Message):
    await message.answer("Список ваших активных клиентов пуст.")

@router.message(F.text == "💰 Финансы")
async def show_finances(message: types.Message):
    await message.answer("Ваш баланс: 0₽. Выплаты производятся автоматически раз в неделю.")

@router.message(F.text == "📹 Контент")
async def show_content_tools(message: types.Message):
    await message.answer("Здесь будут доступны шаблоны для рилсов и советы по продвижению.")

@router.message(F.text == "📈 Статистика")
async def show_stats(message: types.Message):
    await message.answer("Ваша активность за последние 30 дней: 0 занятий.")

@router.message(F.text == "📅 Мои занятия")
async def show_my_bookings(message: types.Message):
    await message.answer("У вас пока нет запланированных занятий.")

@router.message(F.text == "🏆 Рейтинг")
async def show_leaderboard(message: types.Message):
    await message.answer("Вы на 1-м месте среди своих друзей! (Пока что)")

@router.message(F.text == "🔥 Челленджи")
async def show_challenges(message: types.Message):
    await message.answer("Текущий челлендж: '10 000 шагов в день'. Присоединяйтесь!")

@router.message(F.text == "👥 Сообщество")
async def show_community(message: types.Message):
    await message.answer("Присоединяйтесь к нашему чату: @NewFitCommunity")
