import logging
from datetime import datetime, timedelta, timezone
from dateutil.tz import gettz, UTC

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models.models import User, TrainerProfile, ClientProfile, UserRole, Booking, TimeSlot, PROFESSIONAL_ROLES, WorkFormat, Review
from src.utils.db import SessionLocal
from src.keyboards.common import get_trainer_main_kb, get_client_main_kb
from src.keyboards.inline import add_admin_button
from src.utils.text import escape_md

router = Router()
logger = logging.getLogger(__name__)

class GoogleKeysState(StatesGroup):
    waiting_for_client_id = State()
    waiting_for_client_secret = State()

@router.message(F.text.in_(["/profile", "Мой профиль"]))
async def show_profile(message: types.Message, is_admin: bool = False, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer("Вы не зарегистрированы. Используйте /start")
            return

        if user.role in PROFESSIONAL_ROLES:
            stmt = select(TrainerProfile).where(TrainerProfile.user_id == user.id).options(selectinload(TrainerProfile.specializations))
            res = await session.execute(stmt)
            profile = res.scalar_one_or_none()

            if profile:
                specs = ", ".join([s.name for s in profile.specializations]) or "не указаны"
                fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид"}
                work_fmt = profile.work_format.value if hasattr(profile.work_format, 'value') else str(profile.work_format)
                work_fmt_ru = fmt_map.get(work_fmt.upper(), work_fmt.lower())

                username_text = f" (@{escape_md(user.username)})" if user.username else ""
                text = (
                    f"👨‍🏫 **Ваш профиль профессионала**\n\n"
                    f"👤 Имя: {escape_md(user.full_name)}{username_text}\n"
                    f"📞 Телефон: {escape_md(profile.phone) or 'не указан'}\n"
                    f"📍 Город: {escape_md(profile.city)}\n"
                    f"💪 Опыт: {profile.experience} лет\n"
                    f"🎯 Специализации: {escape_md(specs)}\n"
                    f"💰 Цена (разовое): {profile.price_single}₽\n"
                    f"💰 Цена (онлайн): {profile.price_online}₽\n"
                    f"💳 Цена (пакет 12): {profile.price_package}₽\n"
                    f"⭐ Рейтинг: {profile.rating:.1f}\n"
                    f"🏷 Формат: {escape_md(work_fmt_ru)}\n"
                    f"🔗 Ссылка: {escape_md(profile.online_meeting_link) if profile.online_meeting_link else 'не указана'}\n"
                )
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text="📝 Редактировать профиль", callback_data="start_registration")]
                ])
                kb = add_admin_button(kb, is_admin=is_admin)
                await message.answer(text, reply_markup=kb, parse_mode="Markdown")

            has_online = (profile.work_format in [WorkFormat.ONLINE, WorkFormat.HYBRID]) if profile else False
            kb_main = get_trainer_main_kb(is_admin=is_admin, has_online=has_online)
            await message.answer("Управление кабинетом:", reply_markup=kb_main)

        elif user.role == UserRole.CLIENT:
            from sqlalchemy import func
            cp_stmt = select(ClientProfile).where(ClientProfile.user_id == user_id)
            cp = (await session.execute(cp_stmt)).scalar_one_or_none()

            has_specialists = False
            if cp:
                count_stmt = select(func.count(Booking.id)).where(Booking.client_id == cp.id)
                booking_count = (await session.execute(count_stmt)).scalar_one()
                has_specialists = booking_count > 0

            kb = get_client_main_kb(is_admin=is_admin, has_specialists=has_specialists)
            await message.answer(f"🏋️‍♀️ **Личный кабинет клиента**\n\n👤 Имя: {escape_md(user.full_name)}", reply_markup=kb, parse_mode="Markdown")

@router.message(F.text == "🖥 Онлайн тренировка")
async def show_online_training(message: types.Message, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id
    moscow_tz = gettz('Europe/Moscow')
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    future_limit = now_utc + timedelta(days=3)

    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer("Вы не зарегистрированы.")
            return

        if user.role in PROFESSIONAL_ROLES:
            stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user.id)
            profile = (await session.execute(stmt_p)).scalar_one_or_none()
            if not profile:
                await message.answer("Профиль не найден.")
                return

            # Find upcoming online/hybrid slots that are booked in next 3 days
            stmt = (
                select(TimeSlot)
                .where(
                    TimeSlot.trainer_profile_id == profile.id,
                    TimeSlot.status == "booked",
                    TimeSlot.start_time >= now_utc,
                    TimeSlot.start_time <= future_limit
                )
                .options(
                    selectinload(TimeSlot.booking).options(
                        selectinload(Booking.client).options(
                            selectinload(ClientProfile.user)
                        )
                    )
                )
                .order_by(TimeSlot.start_time.asc())
            )
            res = await session.execute(stmt)
            slots = res.scalars().all()

            # Filter online manually to handle "Manicure (online)" etc.
            online_slots = [s for s in slots if ("онлайн" in s.format.lower() or "online" in s.format.lower())]

            if not online_slots:
                await message.answer("У вас нет онлайн тренировок на ближайшие 3 дня.")
                return

            await message.answer(f"🖥 **Ваши онлайн тренировки (на 3 дня):**", parse_mode="Markdown")

            for slot in online_slots:
                start_moscow = slot.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)
                client_name = slot.booking.client.full_name if slot.booking and slot.booking.client else "Клиент"

                text = (
                    f"⏰ `{start_moscow.strftime('%d.%m %H:%M')}`\n"
                    f"👤 Клиент: {escape_md(client_name)}\n"
                    f"🏷 Услуга: {escape_md(slot.format)}\n"
                )

                kb = []
                if slot.online_platform == "telegram":
                    client_user = slot.booking.client.user if slot.booking and slot.booking.client else None
                    if client_user:
                        if client_user.username:
                            kb.append([types.InlineKeyboardButton(text="💬 Написать клиенту", url=f"https://t.me/{client_user.username}")])
                        kb.append([types.InlineKeyboardButton(text="📹 Онлайн тренировка", url=f"tg://user?id={client_user.id}")])
                elif slot.zoom_start_url or slot.zoom_join_url:
                    url = slot.zoom_start_url or slot.zoom_join_url
                    kb.append([types.InlineKeyboardButton(text="🚀 Начать Zoom", url=url)])

                await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb) if kb else None, parse_mode="Markdown")

        else:
            # Client view
            cp_stmt = select(ClientProfile).where(ClientProfile.user_id == user_id)
            client_profile = (await session.execute(cp_stmt)).scalar_one_or_none()
            if not client_profile:
                await message.answer("У вас нет ближайших онлайн тренировок.")
                return

            stmt = (
                select(Booking)
                .where(
                    Booking.client_id == client_profile.id,
                    Booking.start_time >= now_utc,
                    Booking.start_time <= future_limit
                )
                .options(
                    selectinload(Booking.slot).options(
                        selectinload(TimeSlot.trainer_profile).options(
                            selectinload(TrainerProfile.user)
                        )
                    )
                )
                .order_by(Booking.start_time.asc())
            )
            res = await session.execute(stmt)
            bookings = res.scalars().all()

            online_bookings = [b for b in bookings if b.slot and ("онлайн" in b.slot.format.lower() or "online" in b.slot.format.lower())]

            if not online_bookings:
                await message.answer("У вас нет онлайн тренировок на ближайшие 3 дня.")
                return

            await message.answer(f"🖥 **Ваши онлайн тренировки (на 3 дня):**", parse_mode="Markdown")

            for booking in online_bookings:
                slot = booking.slot
                start_moscow = booking.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)
                trainer_name = slot.trainer_profile.user.full_name

                text = (
                    f"⏰ `{start_moscow.strftime('%d.%m %H:%M')}`\n"
                    f"👤 Мастер: {escape_md(trainer_name)}\n"
                    f"🏷 Услуга: {escape_md(slot.format)}\n"
                )

                kb = []
                if slot.online_platform == "telegram":
                    trainer_user = slot.trainer_profile.user
                    if trainer_user:
                        if trainer_user.username:
                            kb.append([types.InlineKeyboardButton(text="💬 Написать мастеру", url=f"https://t.me/{trainer_user.username}")])
                        kb.append([types.InlineKeyboardButton(text="📹 Онлайн тренировка", url=f"tg://user?id={trainer_user.id}")])
                elif slot.zoom_join_url:
                    kb.append([types.InlineKeyboardButton(text="🔗 Войти в Zoom", url=slot.zoom_join_url)])

                await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb) if kb else None, parse_mode="Markdown")

@router.message(F.text == "Мои клиенты")
@router.message(F.text == "/clients")
@router.callback_query(F.data == "clients_list")
async def show_clients(event: types.Message | types.CallbackQuery, effective_user_id: int = None):
    if isinstance(event, types.CallbackQuery):
        user_id = effective_user_id or event.from_user.id
        message = event.message
    else:
        user_id = effective_user_id or event.from_user.id
        message = event
    async with SessionLocal() as session:
        # Get professional profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await message.answer("❌ Профиль профессионала не найден.")
            return

        # Show "My Clients" list for re-booking
        stmt_clients = (
            select(ClientProfile)
            .join(Booking, Booking.client_id == ClientProfile.id)
            .where(Booking.trainer_profile_id == profile.id)
            .distinct()
            .options(selectinload(ClientProfile.user))
        )
        res_clients = await session.execute(stmt_clients)
        unique_clients = res_clients.scalars().all()

        if unique_clients:
            text_clients = "👥 **Ваши клиенты (для повторной записи):**"

            data = await state.get_data()
            slot_id = data.get('slot_id')

            kb_list = []
            for c in unique_clients:
                client_name = c.full_name or f"ID {c.id}"
                callback_data = f"pro_book_client_{c.id}"
                if slot_id:
                    callback_data += f"_{slot_id}"

                kb_list.append([types.InlineKeyboardButton(
                    text=f"Забронировать для {client_name}",
                    callback_data=callback_data
                )])

            await message.answer(text_clients, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb_list), parse_mode="Markdown")
        else:
            await message.answer("У вас пока нет базы клиентов.")

@router.message(F.text == "Мои записи")
@router.message(F.text == "/bookings")
async def show_bookings_router(message: types.Message, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            await message.answer("Вы не зарегистрированы.")
            return

        if user.role in PROFESSIONAL_ROLES:
            await show_pro_bookings(message, user_id)
        else:
            await show_client_bookings_menu(message, user_id)

async def show_pro_bookings(message: types.Message, user_id: int):
    async with SessionLocal() as session:
        moscow_tz = gettz('Europe/Moscow')

        # Get professional profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id).options(selectinload(TrainerProfile.user))
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await message.answer("❌ Профиль профессионала не найден.")
            return

        # Fetch upcoming bookings with client profiles
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            select(Booking)
            .where(
                Booking.trainer_profile_id == profile.id,
                Booking.end_time >= now_utc
            )
            .options(
                selectinload(Booking.client).options(
                    selectinload(ClientProfile.user)
                ),
                selectinload(Booking.slot)
            )
            .order_by(Booking.start_time.asc())
        )
        res = await session.execute(stmt)
        bookings = res.scalars().all()

        if not bookings:
            await message.answer("У вас пока нет предстоящих записей от клиентов.")
        else:
            text = "📅 **Ближайшие записи:**\n\n"
            for b in bookings:
                start_moscow = b.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)
                client_name = b.client.full_name or "Клиент"

                slot_format = b.slot.format if b.slot else ""
                is_specific_sport = any(s in ["Большой теннис", "Падл"] for s in slot_format.split(", "))
                term_format = "Услуга" if (profile.user.role == UserRole.BEAUTY or is_specific_sport) else "Формат"

                text += (
                    f"✅ {start_moscow.strftime('%d.%m %H:%M')}\n"
                    f"👤 Клиент: {escape_md(client_name)}\n"
                    f"🏷 {term_format}: {escape_md(slot_format) or 'не указан'}\n"
                    f"💰 Цена: {int(b.price or 0)}₽\n"
                    f"-------------------\n"
                )
            await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "💰 Финансы и выплаты")
@router.message(F.text == "/earnings")
async def show_finances(message: types.Message):
    await message.answer("Ваш баланс: 0₽. Выплаты производятся автоматически раз в неделю.")

@router.message(F.text == "Статистика")
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

@router.message(F.text == "Поддержка")
async def show_support(message: types.Message):
    await message.answer("Служба поддержки NewFit: @NewFitSupport")

async def show_client_bookings_menu(message: types.Message, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        # Получаем профиль клиента
        cp_stmt = select(ClientProfile).where(ClientProfile.user_id == user_id)
        client_profile = (await session.execute(cp_stmt)).scalar_one_or_none()

        if not client_profile:
            await message.answer("У вас пока нет запланированных занятий.")
            return

        # Fetch unique services (slot formats) from client's upcoming bookings
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = (
            select(TimeSlot.format)
            .join(Booking, Booking.slot_id == TimeSlot.id)
            .where(Booking.client_id == client_profile.id, Booking.start_time >= now_utc)
            .distinct()
        )
        res = await session.execute(stmt)
        services = res.scalars().all()

        if not services:
            await message.answer("У вас пока нет запланированных занятий.")
            return

        kb_list = []
        for svc in services:
            # Clean service name for display and callback
            display_name = svc.split(' (')[0] if '(' in svc else svc
            # Use shorter prefix to avoid Telegram 64-byte callback_data limit
            kb_list.append([types.InlineKeyboardButton(text=display_name, callback_data=f"my_bookings_svc_{svc[:15]}")] )

        await message.answer("Выберите услугу для просмотра записей:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb_list))

@router.callback_query(F.data.startswith("my_bookings_svc_"))
async def show_my_bookings_by_service(callback: types.CallbackQuery, effective_user_id: int = None):
    svc_prefix = callback.data.replace("my_bookings_svc_", "")
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        moscow_tz = gettz('Europe/Moscow')
        cp_stmt = select(ClientProfile).where(ClientProfile.user_id == user_id)
        client_profile = (await session.execute(cp_stmt)).scalar_one_or_none()

        if not client_profile:
            await callback.answer("Профиль не найден")
            return

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        # We search by prefix since we truncated it in callback_data
        stmt = (
            select(Booking)
            .join(TimeSlot)
            .where(
                Booking.client_id == client_profile.id,
                Booking.start_time >= now_utc,
                TimeSlot.format.like(f"{svc_prefix}%")
            )
            .options(
                selectinload(Booking.slot).options(
                    selectinload(TimeSlot.trainer_profile).options(
                        selectinload(TrainerProfile.user)
                    )
                )
            )
            .order_by(Booking.start_time.asc())
        )
        res = await session.execute(stmt)
        bookings = res.scalars().all()

        if not bookings:
            await callback.message.edit_text("Записи по этой услуге не найдены.")
            return

        # Clean display name
        full_svc_name = bookings[0].slot.format
        display_svc = full_svc_name.split(' (')[0] if '(' in full_svc_name else full_svc_name

        await callback.message.edit_text(f"📅 **Ваши записи ({display_svc}):**", parse_mode="Markdown")

        fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид", "offline": "оффлайн", "online": "онлайн", "hybrid": "гибрид"}
        for b in bookings:
            slot = b.slot
            trainer_name = slot.trainer_profile.user.full_name
            status_map = {"confirmed": "✅ Подтверждено", "pending": "⏳ Ожидает", "canceled": "❌ Отменено"}

            # Dynamic labels
            slot_format = slot.format or ""
            is_beauty = slot.trainer_profile.user.role == UserRole.BEAUTY
            is_specific_sport = any(s in ["Большой теннис", "Падл"] for s in slot_format.split(", "))
            term_format = "Услуга" if (is_beauty or is_specific_sport) else "Формат"

            s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
            start_moscow = s_start.astimezone(moscow_tz)

            work_fmt_ru = fmt_map.get(slot_format.lower(), slot_format)

            text = (
                f"👤 Мастер: {escape_md(trainer_name)}\n"
                f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
                f"🏷 {term_format}: {escape_md(work_fmt_ru)}\n"
                f"📊 Статус: {status_map.get(b.status, b.status)}"
            )

            kb = None
            if b.status == "confirmed" and b.start_time < now_utc:
                review_stmt = select(Review).where(Review.booking_id == b.id)
                review_res = await session.execute(review_stmt)
                if not review_res.scalar_one_or_none():
                    kb = types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"leave_review_{b.id}")]
                    ])

            await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.message(F.text == "🏆 Топ мастеров")
async def show_leaderboard(message: types.Message):
    await message.answer("Список самых популярных мастеров месяца.")

@router.message(F.text == "🔥 Челленджи и мотивация")
async def show_challenges(message: types.Message):
    await message.answer("Текущий челлендж: '10 000 шагов в день'. Присоединяйтесь!")

@router.message(F.text == "👥 Сообщество NewFit")
@router.message(F.text == "💬 Мои чаты с профессионалами")
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
async def trainer_menu_redirect(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    await show_profile(callback.message, is_admin=is_admin, effective_user_id=effective_user_id)
    await callback.answer()

@router.message(F.text == "Инструкции")
async def show_instructions_detailed(message: types.Message):
    instruction = (
        "📋 **Инструкция по настройке Google API:**\n\n"
        "1. Зайдите на [console.cloud.google.com](https://console.cloud.google.com/)\n"
        "2. Создайте проект 'NewFit'\n"
        "3. В поиске найдите 'Google Calendar API' и нажмите 'Enable'\n"
        "4. Перейдите in 'Credentials' -> 'Create Credentials' -> 'OAuth client ID'\n"
        "5. Выберите 'Web application'\n"
        "6. Добавьте Authorized redirect URIs: `https://your-bot.railway.app/oauth2callback`\n"
        "7. Скопируйте Client ID and Client Secret и введите их в боте через меню подключения."
    )
    await message.answer(instruction, parse_mode="Markdown", disable_web_page_preview=True)
