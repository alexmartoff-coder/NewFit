from aiogram import Router, F, types, exceptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete, and_
from src.models.models import User, TimeSlot, TrainerSchedule, ScheduleTemplate, WorkFormat, Booking
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from src.utils.text import escape_md
from datetime import datetime, timedelta, time
import logging
import pytz
from dateutil.tz import gettz, UTC

router = Router()
logger = logging.getLogger(__name__)

class ScheduleState(StatesGroup):
    choosing_date = State()
    selecting_dates = State()
    choosing_time = State()
    choosing_duration = State()
    choosing_format = State()
    choosing_platform = State()
    entering_zoom = State()
    entering_capacity = State()
    choosing_price = State()

class GenerateSlotsState(StatesGroup):
    choosing_period = State()
    choosing_format = State()
    choosing_step = State()
    confirming = State()

class TemplateState(StatesGroup):
    choosing_days = State()
    choosing_start_time = State()
    choosing_end_time = State()

@router.message(F.text == "Моё расписание")
@router.message(F.text == "/schedule")
async def show_schedule_menu(message: types.Message, is_admin: bool = False, effective_user_id: int = None, callback: types.CallbackQuery = None, header: str = None):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Посмотреть слоты", callback_data="sche_view")],
            [types.InlineKeyboardButton(text="Быстрая генерация слотов", callback_data="sche_quick_gen")],
            [types.InlineKeyboardButton(text="Забронировать время", callback_data="sche_view_book")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    text = header if header else "Управление вашим расписанием:"

    if callback:
        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
            else:
                await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except exceptions.TelegramBadRequest:
            # Avoid feed clutter if message is identical or edit fails
            await callback.answer()
    else:
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

from src.models.models import TrainerProfile

@router.callback_query(F.data == "sche_view")
async def view_slots(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    # This handler can be called directly from a callback or manually from another handler
    user_id = effective_user_id or callback.from_user.id
    moscow_tz = gettz('Europe/Moscow')

    async with SessionLocal() as session:
        # Resolve profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            text = "❌ Профиль мастера не найден."
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]
            ])
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=kb)
            else:
                await callback.message.edit_text(text, reply_markup=kb)
            return

        now_utc = datetime.now(UTC).replace(tzinfo=None)
        # Fetch slots for the next 30 days to match replenishment/generation
        end_view_utc = now_utc + timedelta(days=30)

        # Group by date for better summary
        from collections import defaultdict
        from sqlalchemy.orm import selectinload

        # Re-fetch with client relationship for booked slots
        stmt = (
            select(TimeSlot)
            .where(
                TimeSlot.trainer_profile_id == profile.id,
                TimeSlot.start_time >= now_utc,
                TimeSlot.start_time <= end_view_utc
            )
            .options(
                selectinload(TimeSlot.booking).options(
                    selectinload(Booking.client)
                )
            )
            .order_by(TimeSlot.start_time.asc())
        )
        res = await session.execute(stmt)
        slots = res.scalars().all()

        # Check for rolling window replenishment
        stmt_config = select(TrainerSchedule).where(TrainerSchedule.trainer_id == user_id)
        res_config = await session.execute(stmt_config)
        config = res_config.scalar_one_or_none()

        if config and config.rolling_window:
            # Maintain the window: check if we have slots for the full duration of the window
            # If we have no slots starting after (window - 1) days, we replenish.
            replenish_threshold = now_utc + timedelta(days=config.rolling_window - 1)
            stmt_future = select(TimeSlot).where(
                TimeSlot.trainer_profile_id == profile.id,
                TimeSlot.start_time >= replenish_threshold
            ).limit(1)
            future_res = await session.execute(stmt_future)

            if not future_res.scalar():
                logger.info(f"Replenishing slots for professional {user_id} (rolling window {config.rolling_window}d)")
                # We use the stored duration and profile's work format
                await generate_slots_from_quick_template(
                    user_id=user_id,
                    days=config.rolling_window,
                    interval=config.slot_duration or 60,
                    work_format=profile.work_format.value if hasattr(profile.work_format, 'value') else str(profile.work_format)
                )
                # Re-fetch slots
                res = await session.execute(stmt)
                slots = res.scalars().all()

        kb_back = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]]
        )
        kb_back = add_admin_button(kb_back, is_admin=is_admin)

        if not slots:
            text = "📭 У вас пока нет запланированных слотов на ближайшее время."
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=kb_back)
            else:
                await callback.message.edit_text(text, reply_markup=kb_back)
            return

        grouped = defaultdict(list)
        for s in slots:
            # Convert UTC from DB to Moscow for grouping and display
            start_moscow = s.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)
            grouped[start_moscow.date()].append(s)

        # Russian day names map
        days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

        full_kb = []
        for date_obj, day_slots in sorted(grouped.items()):
            # Day separator with Russian day name
            day_name = days_ru.get(date_obj.weekday(), "")
            full_kb.append([types.InlineKeyboardButton(text=f"🗓 {date_obj.strftime('%d.%m')} ({day_name})", callback_data="none")])

            row = []
            for s in day_slots:
                # Ensure we handle naive vs aware datetimes consistently
                s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
                start_moscow = s_start.astimezone(moscow_tz)

                status_icon = "🟢" if s.status == "free" else ("🔴" if s.status == "booked" else "⚪")
                btn_text = f"{status_icon} {start_moscow.strftime('%H:%M')}"

                if s.status == "booked" and s.booking and s.booking.client:
                    if row:
                        full_kb.append(row)
                        row = []

                    client_name = s.booking.client.full_name or "Клиент"
                    fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид", "offline": "оффлайн", "online": "онлайн", "hybrid": "гибрид"}
                    fmt_ru = fmt_map.get(s.format, s.format)
                    btn_text += f" 👤 {client_name} ({fmt_ru})"
                    full_kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"view_slot_{s.id}")])
                else:
                    row.append(types.InlineKeyboardButton(text=btn_text, callback_data=f"view_slot_{s.id}"))
                    if len(row) == 3:
                        full_kb.append(row)
                        row = []
            if row:
                full_kb.append(row)

        full_kb.append([types.InlineKeyboardButton(text="Забронировать время", callback_data="sche_view_book")])
        full_kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")])

        actual_days = len(grouped)
        main_text = f"📅 **Ваше расписание (на {actual_days} дней):**"
        kb = types.InlineKeyboardMarkup(inline_keyboard=full_kb)

        # Ensure we edit the message to maintain "popover" behavior
        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=main_text, reply_markup=kb, parse_mode="Markdown")
            else:
                await callback.message.edit_text(text=main_text, reply_markup=kb, parse_mode="Markdown")
        except exceptions.TelegramBadRequest:
            # If for some reason edit fails (e.g. content identical), just answer or fallback
            pass

    await callback.answer()

@router.callback_query(F.data == "sche_add")
async def add_slot_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ScheduleState.choosing_date)
    await callback.message.answer("Введите дату для нового свободного слота (ДД.ММ.ГГГГ):")
    await callback.answer()

@router.message(ScheduleState.choosing_date)
async def add_slot_date(message: types.Message, state: FSMContext):
    try:
        moscow_tz = gettz('Europe/Moscow')
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        today_moscow = datetime.now(moscow_tz).replace(hour=0, minute=0, second=0, microsecond=0)

        if date_obj.replace(tzinfo=moscow_tz) < today_moscow:
            await message.answer("Дата не может быть в прошлом. Попробуйте еще раз:")
            return
        await state.update_data(date=message.text)
        await state.set_state(ScheduleState.choosing_time)
        await message.answer("Введите время начала слота (ЧЧ:ММ):")
    except ValueError:
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ:")

@router.message(ScheduleState.choosing_time)
async def add_slot_time(message: types.Message, state: FSMContext):
    try:
        time_obj = datetime.strptime(message.text, "%H:%M")
        data = await state.get_data()
        date_obj = datetime.strptime(data['date'], "%d.%m.%Y")

        moscow_tz = gettz('Europe/Moscow')
        # User entered time in Moscow
        start_time_moscow = date_obj.replace(hour=time_obj.hour, minute=time_obj.minute, tzinfo=moscow_tz)

        if start_time_moscow < datetime.now(moscow_tz):
            await message.answer("Время не может быть в прошлом.")
            return

        # Save as UTC isoformat
        await state.update_data(start_time_dt=start_time_moscow.astimezone(UTC).isoformat())

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="60 минут", callback_data="as_dur_60")],
            [types.InlineKeyboardButton(text="90 минут", callback_data="as_dur_90")]
        ])
        await message.answer("Выберите длительность:", reply_markup=kb)
        await state.set_state(ScheduleState.choosing_duration)
    except ValueError:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ:")

@router.callback_query(F.data.startswith("as_dur_"), ScheduleState.choosing_duration)
async def add_slot_duration(callback: types.CallbackQuery, state: FSMContext):
    duration = int(callback.data.split("_")[2])
    await state.update_data(duration=duration)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏢 Оффлайн", callback_data="as_fmt_OFFLINE")],
        # Online features temporarily disabled
        # [types.InlineKeyboardButton(text="📱 Онлайн в Telegram", callback_data="as_fmt_TG")],
        # [types.InlineKeyboardButton(text="💻 Другой (Zoom/Meet)", callback_data="as_fmt_ONLINE")],
        # [types.InlineKeyboardButton(text="🔄 Гибрид", callback_data="as_fmt_HYBRID")]
    ])
    text = "Выберите формат для этого слота:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(ScheduleState.choosing_format)
    await callback.answer()

@router.callback_query(F.data.startswith("as_fmt_"), ScheduleState.choosing_format)
async def add_slot_format(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    fmt = callback.data.split("_")[2]
    user_id = effective_user_id or callback.from_user.id

    if fmt == "TG":
        await state.update_data(format="ONLINE", online_platform="telegram")
        await callback.message.answer("Выбрано: Онлайн в Telegram. Сколько человек может записаться? (по умолчанию 1):")
        await state.set_state(ScheduleState.entering_capacity)
    elif fmt in ["ONLINE", "HYBRID"]:
        await state.update_data(format=fmt)
        async with SessionLocal() as session:
            stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            profile = (await session.execute(stmt_p)).scalar_one_or_none()

            kb_list = [
                [types.InlineKeyboardButton(text="Telegram Video", callback_data="plat_telegram")],
                [types.InlineKeyboardButton(text="Zoom", callback_data="plat_zoom")]
            ]
            if profile and profile.online_meeting_link:
                kb_list.append([types.InlineKeyboardButton(text="Использовать постоянную ссылку", callback_data="plat_permanent")])

            kb = types.InlineKeyboardMarkup(inline_keyboard=kb_list)
            await callback.message.answer("Выберите платформу для онлайн-занятия:", reply_markup=kb)
            await state.set_state(ScheduleState.choosing_platform)
    else:
        await state.update_data(format=fmt)
        await callback.message.answer("Введите цену для этого занятия (в ₽):")
        await state.set_state(ScheduleState.choosing_price)
    await callback.answer()

@router.callback_query(F.data.startswith("plat_"), ScheduleState.choosing_platform)
async def add_slot_platform(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    platform = callback.data.split("_")[1]
    user_id = effective_user_id or callback.from_user.id

    if platform == "permanent":
        async with SessionLocal() as session:
            stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            profile = (await session.execute(stmt_p)).scalar_one_or_none()
            await state.update_data(online_platform="zoom", zoom_url=profile.online_meeting_link)
        await callback.message.answer(f"Использую вашу ссылку: {profile.online_meeting_link}. Сколько человек может записаться? (по умолчанию 1):")
        await state.set_state(ScheduleState.entering_capacity)
        await callback.answer()
        return

    await state.update_data(online_platform=platform)
    if platform == "zoom":
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Пропустить", callback_data="skip_zoom")]
        ])
        await callback.message.answer("Введите Zoom-ссылку для этого занятия (или нажмите пропустить):", reply_markup=kb)
        await state.set_state(ScheduleState.entering_zoom)
    else:
        await callback.message.answer("Выбрано: Telegram Video. Сколько человек может записаться? (по умолчанию 1):")
        await state.set_state(ScheduleState.entering_capacity)
    await callback.answer()

@router.callback_query(F.data == "skip_zoom", ScheduleState.entering_zoom)
async def skip_zoom(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(zoom_url=None)
    await callback.message.answer("Введите количество участников (по умолчанию 1):")
    await state.set_state(ScheduleState.entering_capacity)
    await callback.answer()

@router.message(ScheduleState.entering_zoom)
async def add_slot_zoom(message: types.Message, state: FSMContext):
    zoom_url = message.text.strip()
    if not (zoom_url.startswith("http://") or zoom_url.startswith("https://")):
        await message.answer("Пожалуйста, введите корректную ссылку (начинающуюся с http:// или https://) или нажмите 'Пропустить'.")
        return
    await state.update_data(zoom_url=zoom_url)
    await message.answer("Zoom-ссылка сохранена. Сколько человек может записаться? (по умолчанию 1):")
    await state.set_state(ScheduleState.entering_capacity)

@router.message(ScheduleState.entering_capacity)
async def add_slot_capacity(message: types.Message, state: FSMContext):
    try:
        capacity = int(message.text)
        await state.update_data(max_clients=capacity)
    except ValueError:
        await state.update_data(max_clients=1)

    await message.answer("Введите цену для этого занятия (в ₽):")
    await state.set_state(ScheduleState.choosing_price)

async def save_new_time_slot(message: types.Message, state: FSMContext, data: dict, user_id: int):
    """Вспомогательная функция для сохранения слота в БД"""
    try:
        # data['start_time_dt'] is UTC string with timezone info
        start_time_utc = datetime.fromisoformat(data['start_time_dt'])
        # Store as naive UTC in DB
        start_time = start_time_utc.astimezone(UTC).replace(tzinfo=None)

        duration = data['duration']
        end_time = start_time + timedelta(minutes=duration)
        price = data['price']
        max_clients = data.get('max_clients', 1)

        async with SessionLocal() as session:
            # Resolve profile
            stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            profile = (await session.execute(stmt_p)).scalar_one_or_none()
            if not profile:
                await message.answer("❌ Профиль мастера не найден.")
                await state.clear()
                return

            # Проверка на пересечения
            stmt_overlap = select(TimeSlot).where(
                TimeSlot.trainer_profile_id == profile.id,
                and_(
                    TimeSlot.start_time < end_time,
                    TimeSlot.end_time > start_time
                )
            ).limit(1)
            overlap_res = await session.execute(stmt_overlap)
            if overlap_res.scalar():
                await message.answer("❌ Ошибка: В это время у вас уже есть другой слот!")
                await state.clear()
                return

            new_slot = TimeSlot(
                trainer_profile_id=profile.id,
                start_time=start_time,
                end_time=end_time,
                status="free",
                format=str(data['format']),
                price=price,
                max_clients=max_clients,
                zoom_join_url=data.get('zoom_url'),
                online_platform=data.get('online_platform')
            )
            session.add(new_slot)
            await session.commit()

        await message.answer(f"✅ Слот на {start_time.strftime('%d.%m.%Y %H:%M')} ({duration} мин) успешно добавлен!")
        await state.clear()
    except Exception as e:
        logger.exception("Ошибка при сохранении слота")
        await message.answer("❌ Произошла ошибка при сохранении слота. Попробуйте еще раз.")

@router.message(ScheduleState.choosing_price)
async def add_slot_price(message: types.Message, state: FSMContext, effective_user_id: int = None):
    try:
        # Очистка ввода: убираем пробелы и меняем запятую на точку
        price_text = message.text.strip().replace(' ', '').replace(',', '.')
        price = float(price_text)

        if price < 0:
            await message.answer("❌ Цена не может быть отрицательной.")
            return

        await state.update_data(price=price)
        data = await state.get_data()

        # Определяем ID пользователя (с учетом возможной имитации админом)
        user_id = effective_user_id or message.from_user.id

        await save_new_time_slot(message, state, data, user_id)

    except ValueError:
        await message.answer("❌ Введите корректную цену цифрами (например: 2500)")

@router.callback_query(F.data == "sche_block")
async def block_slot_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите дату и время слота, который нужно заблокировать (ДД.ММ.ГГГГ ЧЧ:ММ):")
    await state.set_state("waiting_for_block_time")
    await callback.answer()

from aiogram.filters import StateFilter

@router.message(F.text, StateFilter("waiting_for_block_time"))
async def process_block_time(message: types.Message, state: FSMContext, effective_user_id: int = None):
    try:
        moscow_tz = gettz('Europe/Moscow')
        # User entered time in Moscow
        dt_moscow = datetime.strptime(message.text, "%d.%m.%Y %H:%M").replace(tzinfo=moscow_tz)
        # Convert to naive UTC for DB operations
        dt_utc = dt_moscow.astimezone(UTC).replace(tzinfo=None)

        user_id = effective_user_id or message.from_user.id
        async with SessionLocal() as session:
            stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            profile = (await session.execute(stmt_p)).scalar_one_or_none()
            if not profile:
                await message.answer("❌ Профиль мастера не найден.")
                return

            stmt = select(TimeSlot).where(TimeSlot.trainer_profile_id == profile.id, TimeSlot.start_time == dt_utc)
            res = await session.execute(stmt)
            slot = res.scalar_one_or_none()

            if not slot:
                # Create a blocked slot if it doesn't exist
                slot = TimeSlot(
                    trainer_profile_id=profile.id,
                    start_time=dt_utc,
                    end_time=dt_utc + timedelta(minutes=60),
                    status="blocked",
                    format="hybrid"
                )
                session.add(slot)
            else:
                slot.status = "blocked"

            await session.commit()
        await message.answer(f"Время {message.text} заблокировано.")
        await state.clear()
    except ValueError:
        await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ ЧЧ:ММ")

@router.callback_query(F.data == "sche_template_menu")
async def template_menu(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
        stmt = select(ScheduleTemplate).where(ScheduleTemplate.trainer_id == user_id)
        res = await session.execute(stmt)
        templates = res.scalars().all()

        days_map = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

        text = "Ваши шаблоны (повторяющиеся слоты):\n\n"
        if not templates:
            text += "У вас пока нет шаблонов."
        else:
            for t in templates:
                text += f"• {days_map[t.day_of_week]}: {t.start_time}-{t.end_time}\n"

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Добавить шаблон", callback_data="temp_add")],
            [types.InlineKeyboardButton(text="🗑 Очистить всё", callback_data="temp_clear")],
            [types.InlineKeyboardButton(text="🔧 Настройка длительности", callback_data="sche_config_duration")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]
        ])
        kb = add_admin_button(kb, is_admin=is_admin)
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "temp_clear")
async def temp_clear(callback: types.CallbackQuery, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
        await session.execute(delete(ScheduleTemplate).where(ScheduleTemplate.trainer_id == user_id))
        await session.commit()
    await callback.message.answer("Все шаблоны удалены.")
    await callback.answer()

@router.callback_query(F.data == "temp_add")
async def temp_add_start(callback: types.CallbackQuery, state: FSMContext):
    days = [
        ("Пн", "0"), ("Вт", "1"), ("Ср", "2"), ("Чт", "3"),
        ("Пт", "4"), ("Сб", "5"), ("Вс", "6")
    ]
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=d[0], callback_data=f"tday_{d[1]}") for d in days[:4]],
        [types.InlineKeyboardButton(text=d[0], callback_data=f"tday_{d[1]}") for d in days[4:]]
    ])
    text = "Выберите день недели:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(TemplateState.choosing_days)

@router.callback_query(F.data.startswith("tday_"), TemplateState.choosing_days)
async def temp_add_day(callback: types.CallbackQuery, state: FSMContext):
    day = int(callback.data.split("_")[1])
    await state.update_data(day=day)
    await callback.message.answer("Введите время начала (ЧЧ:ММ), например 10:00:")
    await state.set_state(TemplateState.choosing_start_time)
    await callback.answer()

@router.message(TemplateState.choosing_start_time)
async def temp_add_start_time(message: types.Message, state: FSMContext):
    # Validation simplified for now
    await state.update_data(start_time=message.text)
    await message.answer("Введите время конца (ЧЧ:ММ):")
    await state.set_state(TemplateState.choosing_end_time)

@router.message(TemplateState.choosing_end_time)
async def temp_add_end_time(message: types.Message, state: FSMContext, effective_user_id: int = None):
    data = await state.get_data()
    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        new_temp = ScheduleTemplate(
            trainer_id=user_id,
            day_of_week=data['day'],
            start_time=data['start_time'],
            end_time=message.text
        )
        session.add(new_temp)
        await session.commit()
    await message.answer("Шаблон добавлен! Теперь вы можете сгенерировать слоты из меню.")
    await state.clear()

@router.callback_query(F.data == "sche_quick_gen")
async def quick_gen_start(callback: types.CallbackQuery, state: FSMContext):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="На 7 дней", callback_data="gen_p_7")],
        [types.InlineKeyboardButton(text="На 14 дней", callback_data="gen_p_14")],
        [types.InlineKeyboardButton(text="На 30 дней", callback_data="gen_p_30")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]
    ])
    text = "Выберите период генерации слотов:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(GenerateSlotsState.choosing_period)
    await callback.answer()

@router.callback_query(F.data.startswith("gen_p_"), GenerateSlotsState.choosing_period)
async def quick_gen_period(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    period = int(callback.data.split("_")[2])
    await state.update_data(period=period)
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        from src.models.models import User, UserRole
        user = await session.get(User, user_id)

        # For Beauty, skip format selection and jump to step selection
        if user and str(user.role) == UserRole.BEAUTY.value:
            await state.update_data(gen_format="OFFLINE")

            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="60 минут", callback_data="gen_s_60")],
                [types.InlineKeyboardButton(text="90 минут", callback_data="gen_s_90")],
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_quick_gen")]
            ])
            text = "Выберите шаг между слотами:"
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=kb)
            else:
                await callback.message.edit_text(text, reply_markup=kb)
            await state.set_state(GenerateSlotsState.choosing_step)
            await callback.answer()
            return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Оффлайн", callback_data="gen_f_OFFLINE")],
        # Online features temporarily disabled
        # [types.InlineKeyboardButton(text="Онлайн", callback_data="gen_f_ONLINE")],
        # [types.InlineKeyboardButton(text="Гибрид", callback_data="gen_f_HYBRID")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_quick_gen")]
    ])
    text = "Выберите формат занятий для генерации:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(GenerateSlotsState.choosing_format)
    await callback.answer()

@router.callback_query(F.data.startswith("gen_f_"), GenerateSlotsState.choosing_format)
async def quick_gen_format(callback: types.CallbackQuery, state: FSMContext):
    fmt = callback.data.split("_")[2]
    await state.update_data(gen_format=fmt)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="60 минут", callback_data="gen_s_60")],
        [types.InlineKeyboardButton(text="90 минут", callback_data="gen_s_90")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_quick_gen")]
    ])
    text = "Выберите шаг между слотами:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(GenerateSlotsState.choosing_step)
    await callback.answer()

@router.callback_query(F.data.startswith("gen_s_"), GenerateSlotsState.choosing_step)
async def quick_gen_step(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    step = int(callback.data.split("_")[2])
    await state.update_data(step=step)
    data = await state.get_data()
    period = data['period']

    text = (
        f"📊 **Предпросмотр генерации**\n\n"
        f"🗓 Период: {period} дней\n"
        f"⏱ Шаг: {step} минут\n"
        f"🏢 Режим: Будни (07:00-23:00), Выходные (09:00-22:00)\n"
        f"🏷 Формат: Гибрид\n\n"
        f"Слоты будут созданы только на свободное время. Продолжить?"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🚀 Сгенерировать", callback_data="gen_confirm")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="sche_back")]
    ])
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await state.set_state(GenerateSlotsState.confirming)
    await callback.answer()

@router.callback_query(F.data == "gen_confirm", GenerateSlotsState.confirming)
async def quick_gen_confirm(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    data = await state.get_data()
    user_id = effective_user_id or callback.from_user.id

    msg = "⏳ Генерирую слоты, пожалуйста, подождите..."
    if callback.message.photo:
        await callback.message.edit_caption(caption=msg)
    else:
        await callback.message.edit_text(msg)

    try:
        # Save rolling window preference and parameters
        async with SessionLocal() as session:
            stmt = select(TrainerSchedule).where(TrainerSchedule.trainer_id == user_id)
            res = await session.execute(stmt)
            config = res.scalar_one_or_none()
            if config:
                config.rolling_window = data['period']
                config.slot_duration = data['step']
                config.last_replenished = datetime.now(UTC).replace(tzinfo=None)
                await session.commit()

        count = await generate_slots_from_quick_template(
            user_id=user_id,
            days=data['period'],
            interval=data['step'],
            work_format=data.get('gen_format', 'hybrid')
        )
        report = f"✅ Успешно! Сгенерировано новых слотов: {count}.\n🔄 Автогенерация на {data['period']} дн. включена."
    except Exception as e:
        logger.exception("Ошибка при быстрой генерации слотов")
        report = "❌ Произошла ошибка при генерации. Попробуйте еще раз или обратитесь в поддержку."

    await state.clear()
    await show_schedule_menu(callback.message, effective_user_id=user_id, callback=callback, header=report)
    await callback.answer()

async def generate_slots_from_quick_template(user_id: int, days: int, interval: int, work_format: str = "OFFLINE") -> int:
    from dateutil.tz import gettz, UTC
    from datetime import datetime, time, timedelta
    from dateutil.rrule import rrule, DAILY, MO, TU, WE, TH, FR, SA, SU
    import logging

    logger = logging.getLogger(__name__)
    moscow_tz = gettz('Europe/Moscow')

    async with SessionLocal() as session:
        # Получаем профиль тренера ОДИН РАЗ
        profile_stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(profile_stmt)).scalar_one_or_none()

        if not profile:
            logger.error(f"TrainerProfile not found for user {user_id}")
            return 0

        default_price = float(profile.price_single or 2500.0)
        count = 0

        now_moscow = datetime.now(moscow_tz)
        # We always generate for the next 'days' days from today to ensure the window is full
        start_date = now_moscow.date()
        end_date = start_date + timedelta(days=days)

        for rule in [
            rrule(DAILY, dtstart=datetime.combine(start_date, time.min), until=datetime.combine(end_date, time.max), byweekday=(MO, TU, WE, TH, FR)),
            rrule(DAILY, dtstart=datetime.combine(start_date, time.min), until=datetime.combine(end_date, time.max), byweekday=(SA, SU))
        ]:
            for day_dt in rule:
                day = day_dt.date()
                is_weekend = day.weekday() >= 5
                start_h = 9 if is_weekend else 7
                end_h = 22 if is_weekend else 23

                current = datetime.combine(day, time(start_h, 0)).replace(tzinfo=moscow_tz)

                while current.hour < end_h:
                    end_slot = current + timedelta(minutes=interval)
                    if end_slot.hour > end_h + 1:  # небольшой запас
                        break

                    start_utc = current.astimezone(UTC).replace(tzinfo=None)
                    end_utc = end_slot.astimezone(UTC).replace(tzinfo=None)

                    # Пропускаем слоты в прошлом
                    if current < now_moscow:
                        current += timedelta(minutes=interval)
                        continue

                    # Проверка пересечения
                    overlap = await session.execute(
                        select(TimeSlot).where(
                            TimeSlot.trainer_profile_id == profile.id,
                            TimeSlot.start_time < end_utc,
                            TimeSlot.end_time > start_utc
                        )
                    )
                    if overlap.scalar_one_or_none():
                        current += timedelta(minutes=interval)
                        continue

                    # Создаём слот
                    new_slot = TimeSlot(
                        trainer_profile_id=profile.id,      # ← КРИТИЧНО!
                        start_time=start_utc,
                        end_time=end_utc,
                        format=work_format.lower(),
                        price=default_price if work_format.upper() != "ONLINE" else (profile.price_online or default_price),
                        status="free"
                    )
                    session.add(new_slot)
                    await session.flush()
                    count += 1

                    current += timedelta(minutes=interval)

        await session.commit()
        logger.info(f"Generated {count} slots for professional {user_id}")
        return count

@router.callback_query(F.data == "sche_generate")
async def generate_slots_handler(callback: types.CallbackQuery, effective_user_id: int = None):
    trainer_id = effective_user_id or callback.from_user.id
    moscow_tz = gettz('Europe/Moscow')
    utc_tz = UTC

    async with SessionLocal() as session:
        # Get profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == trainer_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль не найден!")
            return

        # Get templates and professional config
        stmt = select(ScheduleTemplate).where(ScheduleTemplate.trainer_id == trainer_id, ScheduleTemplate.is_active == True)
        res = await session.execute(stmt)
        templates = res.scalars().all()

        if not templates:
            await callback.answer("Сначала создайте шаблоны!", show_alert=True)
            return

        stmt_config = select(TrainerSchedule).where(TrainerSchedule.trainer_id == trainer_id)
        res_config = await session.execute(stmt_config)
        config = res_config.scalar_one_or_none()
        slot_duration = config.slot_duration if config else 60

        # Get default price from profile
        from src.models.models import TrainerProfile
        stmt_profile = select(TrainerProfile).where(TrainerProfile.user_id == trainer_id)
        res_profile = await session.execute(stmt_profile)
        profile = res_profile.scalar_one_or_none()
        default_price = profile.price_single if profile else 2500.0
        default_format = profile.work_format if profile else WorkFormat.HYBRID

        # Generate for next 14 days
        count = 0
        now_moscow = datetime.now(moscow_tz)
        start_date = now_moscow.date()
        for i in range(14):
            current_date = start_date + timedelta(days=i)
            day_of_week = current_date.weekday()

            for t in templates:
                if t.day_of_week == day_of_week:
                    sh, sm = map(int, t.start_time.split(':'))
                    eh, em = map(int, t.end_time.split(':'))

                    template_start_moscow = datetime.combine(current_date, time(sh, sm)).replace(tzinfo=moscow_tz)
                    template_end_moscow = datetime.combine(current_date, time(eh, em)).replace(tzinfo=moscow_tz)

                    # Split template interval into slots
                    current_slot_start_moscow = template_start_moscow
                    while current_slot_start_moscow + timedelta(minutes=slot_duration) <= template_end_moscow:
                        current_slot_end_moscow = current_slot_start_moscow + timedelta(minutes=slot_duration)

                        slot_start_utc = current_slot_start_moscow.astimezone(UTC).replace(tzinfo=None)
                        slot_end_utc = current_slot_end_moscow.astimezone(UTC).replace(tzinfo=None)

                        if current_slot_start_moscow > now_moscow:
                            # Overlap check
                            overlap_stmt = select(TimeSlot).where(
                                TimeSlot.trainer_profile_id == profile.id,
                                TimeSlot.start_time < slot_end_utc,
                                TimeSlot.end_time > slot_start_utc
                            )
                            overlap_res = await session.execute(overlap_stmt)
                            if not overlap_res.scalar_one_or_none():
                                new_slot = TimeSlot(
                                    trainer_profile_id=profile.id,
                                    start_time=slot_start_utc,
                                    end_time=slot_end_utc,
                                    status="free",
                                    format=str(default_format),
                                    price=default_price
                                )
                                session.add(new_slot)
                                await session.flush()
                                count += 1

                        current_slot_start_moscow = current_slot_end_moscow

        await session.commit()
    await callback.message.answer(f"✅ Генерация завершена. Добавлено слотов: {count} (длительность {slot_duration} мин, цена {default_price}₽)")
    await callback.answer()

@router.callback_query(F.data == "sche_view_book")
async def book_time_submenu(callback: types.CallbackQuery, is_admin: bool = False):
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🏖 Отпуск", callback_data="sche_book_vacation")],
        [types.InlineKeyboardButton(text="🗓 Выходной", callback_data="sche_book_weekend")],
        [types.InlineKeyboardButton(text="👤 Клиент", callback_data="clients_list")],
        [types.InlineKeyboardButton(text="🗑 Удалить слот", callback_data="sche_view_del")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]
    ])
    kb = add_admin_button(kb, is_admin=is_admin)
    text = "Забронировать время:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

async def show_multi_date_picker(message: types.Message, state: FSMContext):
    data = await state.get_data()
    selected_dates = data.get("selected_dates", [])
    block_type = data.get("block_type", "Бронирование")

    moscow_tz = gettz('Europe/Moscow')
    today = datetime.now(moscow_tz).date()

    kb = []
    # Show 30 days in rows of 3
    row = []
    for i in range(30):
        d = today + timedelta(days=i)
        d_iso = d.isoformat()

        is_selected = d_iso in selected_dates
        mark = "✅" if is_selected else ""
        text = f"{mark}{d.strftime('%d.%m')}"

        row.append(types.InlineKeyboardButton(text=text, callback_data=f"block_toggle_{d_iso}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([types.InlineKeyboardButton(text="ГОТОВО", callback_data="block_confirm")])
    kb.append([types.InlineKeyboardButton(text="❌ Отмена", callback_data="sche_back")])

    text = f"📅 **Выберите даты для режима '{block_type}':**\n\nНажмите на даты, чтобы отметить их, затем нажмите «Готово»."

    if message.photo:
        await message.edit_caption(caption=text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    else:
        await message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data.in_(["sche_book_vacation", "sche_book_weekend"]))
async def process_manual_block(callback: types.CallbackQuery, state: FSMContext):
    type_text = "Отпуск" if callback.data == "sche_book_vacation" else "Выходной"
    await state.update_data(block_type=type_text, selected_dates=[])
    await state.set_state(ScheduleState.selecting_dates)
    await show_multi_date_picker(callback.message, state)
    await callback.answer()

@router.callback_query(F.data.startswith("block_toggle_"), ScheduleState.selecting_dates)
async def toggle_block_date(callback: types.CallbackQuery, state: FSMContext):
    date_iso = callback.data.replace("block_toggle_", "")
    data = await state.get_data()
    selected = data.get("selected_dates", [])

    if date_iso in selected:
        selected.remove(date_iso)
    else:
        selected.append(date_iso)

    await state.update_data(selected_dates=selected)
    await show_multi_date_picker(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "block_confirm", ScheduleState.selecting_dates)
async def confirm_manual_block(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    data = await state.get_data()
    selected_dates = data.get("selected_dates", [])
    block_type = data.get("block_type", "Бронирование")
    user_id = effective_user_id or callback.from_user.id

    if not selected_dates:
        await callback.answer("Выберите хотя бы одну дату!", show_alert=True)
        return

    async with SessionLocal() as session:
        # Resolve profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль не найден")
            return

        moscow_tz = gettz('Europe/Moscow')
        booked_info = []

        for d_str in selected_dates:
            d = datetime.fromisoformat(d_str).date()

            # Start and end of day in Moscow time
            start_msk = datetime.combine(d, time.min).replace(tzinfo=moscow_tz)
            end_msk = datetime.combine(d, time.max).replace(tzinfo=moscow_tz)

            # Convert to UTC for DB queries
            start_utc = start_msk.astimezone(UTC).replace(tzinfo=None)
            end_utc = end_msk.astimezone(UTC).replace(tzinfo=None)

            # 1. Check for booked slots
            stmt_booked = select(TimeSlot).where(
                TimeSlot.trainer_profile_id == profile.id,
                TimeSlot.start_time >= start_utc,
                TimeSlot.start_time <= end_utc,
                TimeSlot.status == "booked"
            )
            res_booked = await session.execute(stmt_booked)
            booked_slots = res_booked.scalars().all()
            if booked_slots:
                booked_info.append(f"• {d.strftime('%d.%m')}: {len(booked_slots)} зап.")

            # 2. Delete all free and blocked slots for that day
            stmt_del = delete(TimeSlot).where(
                TimeSlot.trainer_profile_id == profile.id,
                TimeSlot.start_time >= start_utc,
                TimeSlot.start_time <= end_utc,
                TimeSlot.status.in_(["free", "blocked"])
            )
            await session.execute(stmt_del)

            # 3. Create a single dummy blocked slot to indicate the day is unavailable
            # This helps prevent some auto-generation logic from seeing it as 'empty'
            # though quick_gen already checks for overlaps.
            block_slot = TimeSlot(
                trainer_profile_id=profile.id,
                start_time=start_utc,
                end_time=start_utc + timedelta(minutes=1440), # Entire day
                status="blocked",
                format=block_type.lower()
            )
            session.add(block_slot)

        await session.commit()

    report = f"✅ Режим '{block_type}' установлен для {len(selected_dates)} дн."
    if booked_info:
        report += "\n\n⚠️ **Внимание!** На эти даты у вас есть записи клиентов:\n" + "\n".join(booked_info)
        report += "\n\nПожалуйста, свяжитесь с клиентами для переноса."

    await state.clear()
    await show_schedule_menu(callback.message, effective_user_id=user_id, callback=callback, header=report)
    await callback.answer()

@router.callback_query(F.data == "sche_view_del")
async def delete_slot_callback(callback: types.CallbackQuery, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    # For simplicity, we just list slots and allow deletion
    async with SessionLocal() as session:
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль не найден!")
            return

        now_utc = datetime.now(UTC).replace(tzinfo=None)
        stmt = select(TimeSlot).where(
            TimeSlot.trainer_profile_id == profile.id,
            TimeSlot.start_time >= now_utc
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        if not slots:
            await callback.message.answer("Нет слотов для удаления.")
            return

        kb = []
        row = []
        moscow_tz = gettz('Europe/Moscow')
        for s in slots:
            # Convert UTC from DB to Moscow for display
            s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
            start_moscow = s_start.astimezone(moscow_tz)

            btn_text = f"❌ {start_moscow.strftime('%d.%m %H:%M')}"
            row.append(types.InlineKeyboardButton(text=btn_text, callback_data=f"slot_del_conf_{s.id}"))
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")])
        text = "Выберите слот для удаления:"
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        else:
            await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("slot_del_conf_"))
async def process_slot_deletion(callback: types.CallbackQuery, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    slot_id = int(callback.data.split("_")[3])

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"sche_del_free_final_{slot_id}"),
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="sche_view_del")
        ]
    ])
    text = "❓ **Подтвердите удаление**\n\nВы действительно хотите удалить этот свободный слот?"

    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="Markdown")
    except exceptions.TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("sche_del_free_final_"))
async def process_slot_deletion_final(callback: types.CallbackQuery, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    slot_id = int(callback.data.split("_")[4])
    async with SessionLocal() as session:
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль не найден!")
            return

        await session.execute(delete(TimeSlot).where(TimeSlot.id == slot_id, TimeSlot.trainer_profile_id == profile.id))
        await session.commit()
    await callback.answer("Слот удалён.", show_alert=True)
    # Refresh the deletion view
    await delete_slot_callback(callback, effective_user_id=effective_user_id)

@router.callback_query(F.data == "sche_config_duration")
async def config_duration_start(callback: types.CallbackQuery, state: FSMContext):
    text = "Введите стандартную длительность в минутах (например, 60 или 90):"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await state.set_state("waiting_for_duration")
    await callback.answer()

@router.message(F.text, StateFilter("waiting_for_duration"))
async def process_config_duration(message: types.Message, state: FSMContext, effective_user_id: int = None):
    try:
        duration = int(message.text)
        user_id = effective_user_id or message.from_user.id
        async with SessionLocal() as session:
            stmt = select(TrainerSchedule).where(TrainerSchedule.trainer_id == user_id)
            res = await session.execute(stmt)
            config = res.scalar_one_or_none()

            if not config:
                config = TrainerSchedule(trainer_id=user_id, slot_duration=duration)
                session.add(config)
            else:
                config.slot_duration = duration

            await session.commit()
        await message.answer(f"Длительность установлена: {duration} мин.")
        await state.clear()
    except ValueError:
        await message.answer("Введите число.")

@router.callback_query(F.data.startswith("view_slot_"))
async def view_slot_info_details(callback: types.CallbackQuery):
    """
    Restores the interactive popover behavior for time slots.
    Edits the current message to show details instead of sending a new one.
    """
    # Callback format: view_slot_{id}
    try:
        slot_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("Ошибка в данных слота.")
        return

    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(TimeSlot)
            .where(TimeSlot.id == slot_id)
            .options(
                selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user),
                selectinload(TimeSlot.booking).options(
                    selectinload(Booking.client)
                )
            )
        )
        res = await session.execute(stmt)
        slot = res.scalars().first()

        if not slot:
            await callback.answer("Слот не найден.")
            return

        # Time formatting
        moscow_tz = gettz('Europe/Moscow')
        s_start = slot.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)
        s_end = slot.end_time.replace(tzinfo=UTC).astimezone(moscow_tz)

        status_map = {"free": "Свободен 🟢", "booked": "Забронирован 🔴", "blocked": "Заблокирован ⚪"}
        fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид", "offline": "оффлайн", "online": "онлайн", "hybrid": "гибрид"}

        status_text = status_map.get(slot.status, slot.status)
        fmt_text = fmt_map.get(slot.format, slot.format)
        trainer_name = slot.trainer_profile.user.full_name

        # Acknowledge the callback silently.
        # All slot details and management buttons are shown via message editing (popover).
        await callback.answer()

        details = (
            f"📍 *Управление слотом*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 *Мастер:* {escape_md(trainer_name)}\n"
            f"📅 *Дата:* {s_start.strftime('%d.%m.%Y')}\n"
            f"⏰ *Время:* `{s_start.strftime('%H:%M')} — {s_end.strftime('%H:%M')}` (МСК)\n"
            f"📊 *Статус:* {status_text}\n"
        )

        if slot.status == "booked":
            client_name = slot.booking.client.full_name if (slot.booking and slot.booking.client) else "Клиент"
            details += f"👤 *Клиент:* {escape_md(client_name)}\n"

        details += f"📍 *Формат:* {fmt_text}\n"
        details += f"💰 *Цена:* {int(slot.price)}₽\n"

        # Online platforms temporarily disabled
        # if slot.online_platform == "telegram":
        #     details += "📱 *Видео:* Telegram\n"
        # elif slot.zoom_join_url:
        #     details += f"🔗 *Zoom:* {escape_md(slot.zoom_join_url)}\n"

        details += "\n━━━━━━━━━━━━━━━━━━"

        kb_list = []
        if slot.status == "free":
            kb_list.append([types.InlineKeyboardButton(text="✅ Забронировать время", callback_data=f"sche_assign_client_{slot.id}")])
            kb_list.append([
                types.InlineKeyboardButton(text="🏖 Отпуск", callback_data=f"sche_day_vacation_{slot.id}"),
                types.InlineKeyboardButton(text="🗓 Выходной", callback_data=f"sche_day_weekend_{slot.id}")
            ])
            kb_list.append([
                types.InlineKeyboardButton(text="🔒 Блок", callback_data=f"sche_block_slot_{slot.id}"),
                types.InlineKeyboardButton(text="🗑 Удалить", callback_data=f"sche_delete_specific_{slot.id}")
            ])
        elif slot.status == "booked":
            client_id = slot.booking.client.id if slot.booking and slot.booking.client else None
            if client_id:
                kb_list.append([types.InlineKeyboardButton(text="🔄 Повторная запись", callback_data=f"pro_book_client_{client_id}")])
            kb_list.append([types.InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"sche_cancel_booking_{slot.id}")])
        elif slot.status == "blocked":
            kb_list.append([types.InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"sche_unblock_slot_{slot.id}")])

        kb_list.append([types.InlineKeyboardButton(text="Назад", callback_data="sche_view")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=kb_list)

        try:
            if callback.message.photo:
                await callback.message.edit_caption(caption=details, reply_markup=kb, parse_mode="Markdown")
            else:
                await callback.message.edit_text(text=details, reply_markup=kb, parse_mode="Markdown")
        except exceptions.TelegramBadRequest:
            pass

@router.callback_query(F.data == "none")
async def none_callback(callback: types.CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "sche_back")
async def sche_back(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    await show_schedule_menu(callback.message, is_admin=is_admin, effective_user_id=effective_user_id, callback=callback)
    await callback.answer()

@router.callback_query(F.data.startswith("sche_block_slot_"))
async def sche_block_slot(callback: types.CallbackQuery):
    slot_id = int(callback.data.split("_")[3])
    async with SessionLocal() as session:
        slot = await session.get(TimeSlot, slot_id)
        if slot:
            slot.status = "blocked"
            await session.commit()
            await callback.answer("Слот заблокирован.", show_alert=True)
            await view_slots(callback)
        else:
            await callback.answer("Слот не найден.")

@router.callback_query(F.data.startswith("sche_unblock_slot_"))
async def sche_unblock_slot(callback: types.CallbackQuery):
    slot_id = int(callback.data.split("_")[3])
    async with SessionLocal() as session:
        slot = await session.get(TimeSlot, slot_id)
        if slot:
            slot.status = "free"
            await session.commit()
            await callback.answer("Слот разблокирован.", show_alert=True)
            await view_slots(callback)
        else:
            await callback.answer("Слот не найден.")

@router.callback_query(F.data.startswith("sche_delete_specific_"))
async def sche_delete_specific(callback: types.CallbackQuery):
    slot_id = int(callback.data.split("_")[3])

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"sche_del_spec_final_{slot_id}"),
            types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"view_slot_{slot_id}")
        ]
    ])
    text = "❓ **Подтвердите удаление**\n\nВы действительно хотите удалить этот слот из расписания?"

    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="Markdown")
    except exceptions.TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("sche_del_spec_final_"))
async def sche_delete_specific_final(callback: types.CallbackQuery):
    slot_id = int(callback.data.split("_")[4])
    async with SessionLocal() as session:
        slot = await session.get(TimeSlot, slot_id)
        if slot:
            await session.delete(slot)
            await session.commit()
            await callback.answer("Слот удалён.", show_alert=True)
            await view_slots(callback)
        else:
            await callback.answer("Слот не найден.")

@router.callback_query(F.data.startswith("sche_cancel_booking_"))
async def sche_cancel_booking(callback: types.CallbackQuery):
    slot_id = int(callback.data.split("_")[3])

    text = "❓ **Отмена записи**\n\nВыберите вариант отмены:"
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔓 Освободить время (для новой записи)", callback_data=f"sche_cancel_confirm_free_{slot_id}")],
        [types.InlineKeyboardButton(text="🗑 Удалить слот (например, заболел)", callback_data=f"sche_cancel_confirm_del_{slot_id}")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"view_slot_{slot_id}")]
    ])

    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="Markdown")
    except exceptions.TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("sche_cancel_confirm_"))
async def sche_cancel_confirm(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    action = parts[3] # free or del
    slot_id = int(parts[4])

    text = "⚠️ **Внимание!**\n\nВы действительно хотите отменить запись клиента? Это действие нельзя отменить, клиент получит уведомление."
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"sche_cancel_final_{action}_{slot_id}"),
            types.InlineKeyboardButton(text="❌ Нет", callback_data=f"sche_cancel_booking_{slot_id}")
        ]
    ])

    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="Markdown")
    except exceptions.TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("sche_cancel_final_"))
async def sche_cancel_confirm_final(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    action = parts[3] # free or del
    slot_id = int(parts[4])

    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.booking).options(selectinload(Booking.client)),
            selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user)
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        if not slot or slot.status != "booked":
            await callback.answer("Запись не найдена или уже отменена.", show_alert=True)
            await view_slots(callback)
            return

        booking = slot.booking
        client_user_id = booking.client.user_id if booking and booking.client else None
        trainer_name = slot.trainer_profile.user.full_name

        moscow_tz = gettz('Europe/Moscow')
        s_start = slot.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)
        slot_time_str = s_start.strftime('%d.%m %H:%M')
        slot_format = slot.format

        # 1. Notify Client
        if client_user_id:
            try:
                msg_to_client = (
                    f"❌ **Запись отменена мастером**\n\n"
                    f"Ваша запись к мастеру {escape_md(trainer_name)} отменена.\n"
                    f"📅 Время: `{slot_time_str}` (МСК)\n"
                    f"🏷 Услуга: {escape_md(slot_format)}\n\n"
                    f"Вы можете выбрать другое время в каталоге."
                )
                await callback.bot.send_message(client_user_id, msg_to_client, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to notify client {client_user_id} about cancellation: {e}")

        # 2. Process Cancellation
        if booking:
            await session.delete(booking)

        if action == "free":
            slot.status = "free"
            slot.client_id = None
            msg_alert = "Запись отменена. Слот снова свободен."
        else: # del
            await session.delete(slot)
            msg_alert = "Запись отменена. Слот удалён из расписания."

        await session.commit()
        await callback.answer(msg_alert, show_alert=True)
        await view_slots(callback)

@router.callback_query(F.data.startswith("sche_day_"))
async def sche_day_action(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    action = parts[2] # vacation or weekend
    slot_id = int(parts[3])
    block_type = "Отпуск" if action == "vacation" else "Выходной"

    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(selectinload(TimeSlot.trainer_profile))
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        if not slot:
            await callback.answer("Слот не найден.")
            return

        profile_id = slot.trainer_profile_id
        moscow_tz = gettz('Europe/Moscow')
        # Get the Moscow date of the slot
        d = slot.start_time.replace(tzinfo=UTC).astimezone(moscow_tz).date()

        # Start and end of day in Moscow time
        start_msk = datetime.combine(d, time.min).replace(tzinfo=moscow_tz)
        end_msk = datetime.combine(d, time.max).replace(tzinfo=moscow_tz)

        # Convert to UTC for DB queries
        start_utc = start_msk.astimezone(UTC).replace(tzinfo=None)
        end_utc = end_msk.astimezone(UTC).replace(tzinfo=None)

        # Check for booked slots
        stmt_booked = select(TimeSlot).where(
            TimeSlot.trainer_profile_id == profile_id,
            TimeSlot.start_time >= start_utc,
            TimeSlot.start_time <= end_utc,
            TimeSlot.status == "booked"
        )
        res_booked = await session.execute(stmt_booked)
        if res_booked.scalars().all():
            await callback.answer(f"⚠️ Невозможно установить {block_type}: на этот день есть записи!", show_alert=True)
            return

        # Delete all free and blocked slots for that day
        stmt_del = delete(TimeSlot).where(
            TimeSlot.trainer_profile_id == profile_id,
            TimeSlot.start_time >= start_utc,
            TimeSlot.start_time <= end_utc,
            TimeSlot.status.in_(["free", "blocked"])
        )
        await session.execute(stmt_del)

        # Create a single dummy blocked slot to indicate the day is unavailable
        block_slot = TimeSlot(
            trainer_profile_id=profile_id,
            start_time=start_utc,
            end_time=start_utc + timedelta(minutes=1440),
            status="blocked",
            format=block_type.lower()
        )
        session.add(block_slot)
        await session.commit()

    await callback.answer(f"✅ Режим '{block_type}' установлен на {d.strftime('%d.%m')}.", show_alert=True)
    await view_slots(callback)

from src.states.pro_booking import ProBookingSession
from src.handlers.profiles import show_clients

@router.callback_query(F.data.startswith("sche_assign_client_"))
async def sche_assign_client_start(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    slot_id = int(callback.data.split("_")[-1])
    await state.set_state(ProBookingSession.choosing_date) # ProBookingSession start state
    await state.update_data(slot_id=slot_id)
    await show_clients(callback, state=state, effective_user_id=effective_user_id)

# --- Catch-all handlers for state consistency ---
@router.message(ScheduleState.choosing_duration)
@router.message(ScheduleState.choosing_format)
@router.message(ScheduleState.choosing_platform)
async def catch_invalid_input(message: types.Message):
    await message.answer("Пожалуйста, используйте кнопки меню для выбора.")

@router.message(GenerateSlotsState.choosing_period)
@router.message(GenerateSlotsState.choosing_format)
@router.message(GenerateSlotsState.choosing_step)
@router.message(GenerateSlotsState.confirming)
async def catch_invalid_gen_input(message: types.Message):
    await message.answer("Пожалуйста, используйте кнопки меню для выбора параметров генерации.")
