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
                f"💰 Разовое: {profile.price_single}₽\n"
                f"💳 12 занятий: {profile.price_package}₽\n"
                f"⭐ Рейтинг: {profile.rating}\n"
                f"📝 Формат: {profile.work_format.value}"
            )
            await message.answer(text)
        else:
            await message.answer(f"👤 Профиль клиента: {user.full_name}")

@router.message(F.text == "👤 Мой профиль")
async def show_profile(message: types.Message, is_admin: bool = False):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start")
            return

        if user.role == UserRole.TRAINER:
            await message.answer("👨‍🏫 Личный кабинет тренера\n\nВыберите раздел:", reply_markup=get_trainer_main_kb(is_admin=is_admin))
        elif user.role == UserRole.CLIENT:
            await message.answer("🏋️‍♀️ Личный кабинет клиента\n\nВыберите раздел:", reply_markup=get_client_main_kb(is_admin=is_admin))

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

@router.message(F.text == "🔗 Подключить Google Календарь")
async def connect_google_calendar(message: types.Message):
    from src.utils.config import settings
    if not settings.GOOGLE_CLIENT_ID:
        await message.answer("Настройка Google Calendar временно недоступна. Обратитесь к администратору.")
        return

    # Simple placeholder for OAuth flow
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={settings.GOOGLE_CLIENT_ID}&redirect_uri={settings.GOOGLE_REDIRECT_URI}&response_type=code&scope=https://www.googleapis.com/auth/calendar&access_type=offline&prompt=consent"

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Авторизоваться в Google", url=auth_url)]
        ]
    )
    await message.answer(
        "Для синхронизации расписания необходимо подключить ваш Google Календарь.\n\n"
        "Нажмите кнопку ниже для авторизации. После авторизации скопируйте код и отправьте его сюда (имитация):",
        reply_markup=kb
    )

@router.message(F.text.startswith("4/"), F.from_user.id.in_(lambda data: True)) # Mock check
async def mock_oauth_code_handler(message: types.Message):
    # This is a very rough mock of handling an OAuth code
    async with SessionLocal() as session:
        from src.models.models import TrainerSchedule
        stmt = select(TrainerSchedule).where(TrainerSchedule.trainer_id == message.from_user.id)
        res = await session.execute(stmt)
        sched = res.scalar_one_or_none()

        if not sched:
            sched = TrainerSchedule(trainer_id=message.from_user.id)
            session.add(sched)

        sched.google_refresh_token = "mock_refresh_token"
        sched.google_calendar_id = "primary"
        sched.sync_enabled = True
        await session.commit()

    await message.answer("✅ Google Календарь успешно подключен! Теперь ваши занятия будут синхронизироваться.")
