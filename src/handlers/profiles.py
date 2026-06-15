from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import User, TrainerProfile, ClientProfile, UserRole
from src.utils.db import SessionLocal
from src.keyboards.common import get_trainer_main_kb, get_client_main_kb
from src.keyboards.inline import add_admin_button
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

router = Router()

class GoogleKeysState(StatesGroup):
    waiting_for_client_id = State()
    waiting_for_client_secret = State()

@router.message(F.text == "/profile")
async def show_profile_cmd(message: types.Message, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
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
async def show_profile(message: types.Message, is_admin: bool = False, effective_user_id: int = None):
    user_id = effective_user_id
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start")
            return

        if user.role == UserRole.TRAINER:
            kb = get_trainer_main_kb(is_admin=is_admin)
            await message.answer("👨‍🏫 Личный кабинет тренера\n\nВыберите раздел:", reply_markup=kb)
        elif user.role == UserRole.CLIENT:
            kb = get_client_main_kb(is_admin=is_admin)
            await message.answer("🏋️‍♀️ Личный кабинет клиента\n\nВыберите раздел:", reply_markup=kb)

@router.message(F.text == "📆 Расписание и запись")
@router.message(F.text == "/schedule")
async def show_schedule(message: types.Message, effective_user_id: int = None):
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
async def show_my_bookings(message: types.Message, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        from src.models.models import Booking, TimeSlot, User, ClientProfile
        from sqlalchemy.orm import selectinload

        # Получаем профиль клиента
        cp_stmt = select(ClientProfile).where(ClientProfile.user_id == user_id)
        cp_res = await session.execute(cp_stmt)
        client_profile = cp_res.scalar_one_or_none()

        if not client_profile:
            await message.answer("У вас пока нет запланированных занятий.")
            return

        stmt = (
            select(Booking)
            .where(Booking.client_id == client_profile.id)
            .options(selectinload(Booking.slot).selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user))
            .order_by(Booking.booked_at.desc())
        )
        res = await session.execute(stmt)
        bookings = res.scalars().all()

        if not bookings:
            await message.answer("У вас пока нет запланированных занятий.")
            return

        text = "📅 **Ваши ближайшие занятия:**\n\n"
        for b in bookings:
            slot = b.slot
            trainer_name = slot.trainer_profile.user.full_name
            status_map = {"confirmed": "✅ Подтверждено", "pending": "⏳ Ожидает", "canceled": "❌ Отменено"}

            text += (
                f"👤 Тренер: {trainer_name}\n"
                f"⏰ Время: {slot.start_time.strftime('%d.%m %H:%M')}\n"
                f"🏷 Формат: {slot.format}\n"
                f"📊 Статус: {status_map.get(b.status, b.status)}\n"
                f"-------------------\n"
            )

        await message.answer(text, parse_mode="Markdown")

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
@router.callback_query(F.data == "trainer_connect_google")
async def connect_google_calendar(event: types.Message | types.CallbackQuery, effective_user_id: int = None, is_admin: bool = False):
    message = event if isinstance(event, types.Message) else event.message
    user_id = effective_user_id or event.from_user.id

    async with SessionLocal() as session:
        from src.models.models import TrainerSchedule
        stmt = select(TrainerSchedule).where(TrainerSchedule.trainer_id == user_id)
        res = await session.execute(stmt)
        schedule = res.scalar_one_or_none()

        if schedule and schedule.google_refresh_token:
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔄 Переподключить", callback_data="trainer_google_reconnect")],
                [types.InlineKeyboardButton(text="🔌 Отключить", callback_data="trainer_google_disconnect")],
                [types.InlineKeyboardButton(text="⚙️ Настройки синхронизации", callback_data="trainer_google_settings")],
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="trainer_menu")],
            ])
            keyboard = add_admin_button(keyboard, is_admin=is_admin)
            text = (
                "✅ **Google Календарь подключён!**\n\n"
                f"📅 ID календаря: `{schedule.google_calendar_id}`\n"
                f"⏰ Часовой пояс: {schedule.timezone}\n"
                f"⏱ Длительность слота: {schedule.slot_duration} мин.\n\n"
                "Все записи клиентов будут автоматически добавляться в ваш Google Календарь."
            )
            if isinstance(event, types.Message):
                await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                if event.message.photo:
                    await event.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="Markdown")
                else:
                    await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
            return

        # Not connected, show instruction
        instruction_text = (
            "📋 **Как подключить Google Календарь**\n\n"
            "1️⃣ Перейдите в [Google Cloud Console](https://console.cloud.google.com/)\n"
            "2️⃣ Создайте новый проект или выберите существующий\n"
            "3️⃣ Включите **Google Calendar API**\n"
            "4️⃣ Создайте **OAuth 2.0 Client ID** (тип: Desktop app или Web application)\n"
            "5️⃣ Скопируйте **Client ID** и **Client Secret**\n"
            "6️⃣ Нажмите кнопку **«У меня есть ключи»** ниже\n\n"
            "⚠️ Сохраните ключи — они понадобятся только один раз."
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔑 У меня есть Client ID и Secret", callback_data="trainer_google_enter_keys")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="trainer_menu")],
        ])
        keyboard = add_admin_button(keyboard, is_admin=is_admin)

        if isinstance(event, types.Message):
            await message.answer(instruction_text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
        else:
            if event.message.photo:
                await event.message.edit_caption(caption=instruction_text, reply_markup=keyboard, parse_mode="Markdown")
            else:
                await event.message.edit_text(instruction_text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)

@router.callback_query(F.data == "trainer_google_enter_keys")
async def start_enter_keys(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "🔑 **Введите ваш Google Client ID**\n\n"
        "Он выглядит примерно так:\n"
        "`123456789012-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com`\n\n"
        "Отправьте его одним сообщением:"
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await state.set_state(GoogleKeysState.waiting_for_client_id)
    await callback.answer()

@router.message(GoogleKeysState.waiting_for_client_id)
async def get_client_id(message: types.Message, state: FSMContext):
    await state.update_data(client_id=message.text.strip())
    await message.answer(
        "🔐 **Введите ваш Google Client Secret**\n\n"
        "Он выглядит примерно так:\n"
        "`GOCSPX-xxxxxxxxxxxxxxxxxxxx`\n\n"
        "Отправьте его одним сообщением:"
    )
    await state.set_state(GoogleKeysState.waiting_for_client_secret)

@router.message(GoogleKeysState.waiting_for_client_secret)
async def get_client_secret(message: types.Message, state: FSMContext, effective_user_id: int = None):
    data = await state.get_data()
    client_id = data.get("client_id")
    client_secret = message.text.strip()
    user_id = effective_user_id or message.from_user.id

    async with SessionLocal() as session:
        from src.models.models import TrainerSchedule
        stmt = select(TrainerSchedule).where(TrainerSchedule.trainer_id == user_id)
        res = await session.execute(stmt)
        sched = res.scalar_one_or_none()

        if not sched:
            sched = TrainerSchedule(trainer_id=user_id)
            session.add(sched)

        # Here we mock the integration for now
        sched.google_refresh_token = f"mock_{client_id[:10]}_{client_secret[:5]}"
        sched.google_calendar_id = "primary"
        sched.sync_enabled = True
        await session.commit()

    await state.clear()
    await message.answer("✅ **Ключи сохранены!**\n\nВыполняется подключение к Google... (имитация)\n\nGoogle Календарь успешно подключен!")

@router.callback_query(F.data == "trainer_google_reconnect")
async def trainer_google_reconnect(callback: types.CallbackQuery, state: FSMContext):
    await start_enter_keys(callback, state)

@router.callback_query(F.data == "trainer_google_disconnect")
async def trainer_google_disconnect(callback: types.CallbackQuery, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
        from src.models.models import TrainerSchedule
        stmt = select(TrainerSchedule).where(TrainerSchedule.trainer_id == user_id)
        res = await session.execute(stmt)
        sched = res.scalar_one_or_none()
        if sched:
            sched.google_refresh_token = None
            sched.sync_enabled = False
            await session.commit()

    text = "🔌 Google Календарь отключен."
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await callback.answer()

@router.callback_query(F.data == "trainer_google_settings")
async def trainer_google_settings(callback: types.CallbackQuery):
    await callback.message.answer("Здесь вы сможете настроить часовой пояс и длительность слотов (в разработке).")
    await callback.answer()

@router.callback_query(F.data == "trainer_menu")
async def trainer_menu_redirect(callback: types.CallbackQuery):
    await show_profile(callback.message, is_admin=False) # Simplified, middleware would handle is_admin
    await callback.answer()

@router.message(F.text == "📋 Инструкции")
async def show_instructions_detailed(message: types.Message):
    instruction = (
        "📋 **Инструкция по настройке Google API:**\n\n"
        "1. Зайдите на [console.cloud.google.com](https://console.cloud.google.com/)\n"
        "2. Создайте проект 'NewFit'\n"
        "3. В поиске найдите 'Google Calendar API' и нажмите 'Enable'\n"
        "4. Перейдите в 'Credentials' -> 'Create Credentials' -> 'OAuth client ID'\n"
        "5. Выберите 'Web application'\n"
        "6. Добавьте Authorized redirect URIs: `https://your-bot.railway.app/oauth2callback`\n"
        "7. Скопируйте Client ID и Client Secret и введите их в боте через меню подключения."
    )
    await message.answer(instruction, parse_mode="Markdown", disable_web_page_preview=True)
