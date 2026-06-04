from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import User, TrainerProfile, ClientProfile, UserRole
from src.utils.db import SessionLocal
from src.keyboards.common import get_trainer_main_kb, get_client_main_kb

router = Router()

@router.message(F.text == "/profile")
async def show_profile_cmd(message: types.Message):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start")
            return

        if user.role == UserRole.TRAINER:
            query = select(TrainerProfile).where(TrainerProfile.user_id == user.id)
            result = await session.execute(query)
            profile = result.scalar_one_or_none()
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
            await message.answer(f"👤 Профиль клиента: {user.full_name}")

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start")
            return

        if user.role == UserRole.TRAINER:
            await message.answer("👨‍🏫 Личный кабинет тренера\n\nВыберите раздел:", reply_markup=get_trainer_main_kb())
        elif user.role == UserRole.CLIENT:
            await message.answer("🏋️‍♀️ Личный кабинет клиента\n\nВыберите раздел:", reply_markup=get_client_main_kb())

@router.message(F.text == "📆 Расписание и запись")
@router.message(F.text == "/schedule")
async def show_schedule(message: types.Message):
    await message.answer("Ваше расписание на сегодня пусто. Интеграция с Google Calendar будет доступна в следующем обновлении.")

@router.message(F.text == "👥 Мои клиенты")
@router.message(F.text == "/clients")
async def show_clients(message: types.Message):
    await message.answer("Список ваших активных клиентов пуст.")

@router.message(F.text == "💰 Финансы и выплаты")
@router.message(F.text == "/earnings")
async def show_finances(message: types.Message):
    await message.answer("Ваш баланс: 0₽. Выплаты производятся автоматически раз в неделю.")

@router.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    await message.answer("Ваша активность за последние 30 дней: 0 занятий.")

@router.message(F.text == "📹 Создать контент (рилсы)")
async def show_content_tools(message: types.Message):
    await message.answer("Здесь будут доступны шаблоны для рилсов и советы по продвижению.")

@router.message(F.text == "🚀 Продвижение")
async def show_promotion(message: types.Message):
    await message.answer("Заявка на помощь в продвижении отправлена администраторам.")

@router.message(F.text == "⭐ Повысить видимость")
async def show_premium(message: types.Message):
    await message.answer("Подключите Премиум (990₽/мес) для приоритета в поиске!")

@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: types.Message):
    await message.answer("Настройки профиля и уведомлений.")

@router.message(F.text == "❓ Поддержка")
async def show_support(message: types.Message):
    await message.answer("Служба поддержки NewFit: @NewFitSupport")

@router.message(F.text == "📋 Инструкции")
async def show_instructions(message: types.Message):
    await message.answer("Инструкции по проведению гибридных тренировок и использованию бота.")

@router.message(F.text == "📅 Мои занятия и абонементы")
async def show_my_bookings(message: types.Message):
    await message.answer("У вас пока нет запланированных занятий.")

@router.message(F.text == "🏆 Топ тренеров")
async def show_leaderboard(message: types.Message):
    await message.answer("Список самых популярных тренеров месяца.")

@router.message(F.text == "🔥 Челленджи и мотивация")
async def show_challenges(message: types.Message):
    await message.answer("Текущий челлендж: '10 000 шагов в день'. Присоединяйтесь!")

@router.message(F.text == "👥 Сообщество NewFit")
@router.message(F.text == "💬 Мои чаты с тренерами")
async def show_chats(message: types.Message):
    await message.answer("У вас пока нет активных диалогов.")
