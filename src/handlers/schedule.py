from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete, and_
from src.models.models import User, TimeSlot, TrainerSchedule, ScheduleTemplate, WorkFormat, Booking
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from datetime import datetime, timedelta, time
import logging
import pytz
from dateutil.tz import gettz, UTC

router = Router()
logger = logging.getLogger(__name__)

class ScheduleState(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    choosing_duration = State()
    choosing_format = State()
    choosing_price = State()

class GenerateSlotsState(StatesGroup):
    choosing_period = State()
    choosing_step = State()
    confirming = State()

class TemplateState(StatesGroup):
    choosing_days = State()
    choosing_start_time = State()
    choosing_end_time = State()

@router.message(F.text == "📅 Моё расписание")
@router.message(F.text == "/schedule")
async def show_schedule_menu(message: types.Message, is_admin: bool = False, effective_user_id: int = None):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📅 Просмотреть слоты", callback_data="sche_view")],
            [types.InlineKeyboardButton(text="➕ Создать новый слот", callback_data="sche_add")],
            [types.InlineKeyboardButton(text="⚡ Быстрая генерация слотов", callback_data="sche_quick_gen")],
            [types.InlineKeyboardButton(text="🔁 Повторяющееся расписание", callback_data="sche_template_menu")],
            [types.InlineKeyboardButton(text="⚡ Сгенерировать по моим шаблонам", callback_data="sche_generate")],
            [types.InlineKeyboardButton(text="🚫 Заблокировать время", callback_data="sche_block")],
            [types.InlineKeyboardButton(text="🗑 Удалить слот", callback_data="sche_view_del")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer("Управление вашим расписанием:", reply_markup=kb)

from src.models.models import TrainerProfile

@router.callback_query(F.data == "sche_view")
async def view_slots(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    moscow_tz = gettz('Europe/Moscow')

    async with SessionLocal() as session:
        # Resolve profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            text = "❌ Профиль тренера не найден."
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]
            ])
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=kb)
            else:
                await callback.message.edit_text(text, reply_markup=kb)
            return

        now_utc = datetime.now(UTC).replace(tzinfo=None)
        # Fetch slots for the next 14 days
        end_view_utc = now_utc + timedelta(days=14)

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
            .options(selectinload(TimeSlot.booking).selectinload(Booking.client))
            .order_by(TimeSlot.start_time.asc())
        )
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

        text = "📅 **Ваше расписание на 14 дней (МСК):**\n\n"
        fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид"}
        for date_obj, day_slots in sorted(grouped.items()):
            text += f"🗓 `{date_obj.strftime('%d.%m (%a)')}`\n"
            for s in day_slots:
                # Ensure we handle naive vs aware datetimes consistently
                s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
                s_end = s.end_time.replace(tzinfo=UTC) if s.end_time.tzinfo is None else s.end_time.astimezone(UTC)

                start_moscow = s_start.astimezone(moscow_tz)
                end_moscow = s_end.astimezone(moscow_tz)

                status_icon = "🟢" if s.status == "free" else ("🔴" if s.status == "booked" else "⚪")
                fmt_val = s.format.value if hasattr(s.format, 'value') else str(s.format)
                fmt_ru = fmt_map.get(fmt_val, fmt_val.lower())

                info = f"{start_moscow.strftime('%H:%M')}—{end_moscow.strftime('%H:%M')} | {int(s.price)}₽ ({fmt_ru})"
                if s.status == "booked" and s.booking and s.booking.client:
                    client_name = s.booking.client.full_name or "Клиент"
                    info += f" — 👤 {client_name}"

                text += f"  {status_icon} {info}\n"
            text += "\n"

        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb_back, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text, reply_markup=kb_back, parse_mode="Markdown")
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
        await message.answer("Выберите длительность занятия:", reply_markup=kb)
        await state.set_state(ScheduleState.choosing_duration)
    except ValueError:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ:")

@router.callback_query(F.data.startswith("as_dur_"), ScheduleState.choosing_duration)
async def add_slot_duration(callback: types.CallbackQuery, state: FSMContext):
    duration = int(callback.data.split("_")[2])
    await state.update_data(duration=duration)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Оффлайн", callback_data="as_fmt_OFFLINE")],
        [types.InlineKeyboardButton(text="Онлайн", callback_data="as_fmt_ONLINE")],
        [types.InlineKeyboardButton(text="Гибрид", callback_data="as_fmt_HYBRID")]
    ])
    text = "Выберите формат для этого слота:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(ScheduleState.choosing_format)
    await callback.answer()

@router.callback_query(F.data.startswith("as_fmt_"), ScheduleState.choosing_format)
async def add_slot_format(callback: types.CallbackQuery, state: FSMContext):
    fmt = callback.data.split("_")[2]
    await state.update_data(format=fmt)
    await callback.message.answer("Введите цену для этого занятия (в ₽):")
    await state.set_state(ScheduleState.choosing_price)
    await callback.answer()

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

        async with SessionLocal() as session:
            # Resolve profile
            stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            profile = (await session.execute(stmt_p)).scalar_one_or_none()
            if not profile:
                await message.answer("❌ Профиль тренера не найден.")
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
                price=price
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

@router.message(F.text, F.state == "waiting_for_block_time")
async def process_block_time(message: types.Message, state: FSMContext, effective_user_id: int = None):
    try:
        dt = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        user_id = effective_user_id or message.from_user.id
        async with SessionLocal() as session:
            stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            profile = (await session.execute(stmt_p)).scalar_one_or_none()
            if not profile:
                await message.answer("❌ Профиль тренера не найден.")
                return

            stmt = select(TimeSlot).where(TimeSlot.trainer_profile_id == profile.id, TimeSlot.start_time == dt)
            res = await session.execute(stmt)
            slot = res.scalar_one_or_none()

            if not slot:
                # Create a blocked slot if it doesn't exist
                slot = TimeSlot(
                    trainer_profile_id=profile.id,
                    start_time=dt,
                    end_time=dt + timedelta(minutes=60),
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
async def quick_gen_period(callback: types.CallbackQuery, state: FSMContext):
    period = int(callback.data.split("_")[2])
    await state.update_data(period=period)

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
        count = await generate_slots_from_quick_template(
            user_id=user_id,
            days=data['period'],
            interval=data['step']
        )
        await callback.message.answer(f"✅ Успешно! Сгенерировано новых слотов: {count}")
    except Exception as e:
        logger.exception("Ошибка при быстрой генерации слотов")
        await callback.message.answer("❌ Произошла ошибка при генерации. Попробуйте еще раз или обратитесь в поддержку.")

    await state.clear()
    await show_schedule_menu(callback.message, effective_user_id=user_id)
    await callback.answer()

async def generate_slots_from_quick_template(user_id: int, days: int, interval: int) -> int:
    from dateutil.tz import gettz, UTC
    from datetime import datetime, time, timedelta
    from dateutil.rrule import rrule, DAILY, MO, TU, WE, TH, FR, SA, SU

    moscow_tz = gettz('Europe/Moscow')
    now_moscow = datetime.now(moscow_tz)

    start_date = now_moscow.date()
    end_date = start_date + timedelta(days=days)

    async with SessionLocal() as session:
        # Получаем профиль
        profile_stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(profile_stmt)).scalar_one_or_none()
        if not profile:
            return 0

        default_price = float(profile.price_single or 2500.0)
        count = 0

        # Правила для будней и выходных
        rules = [
            rrule(DAILY, dtstart=datetime.combine(start_date, time.min), until=datetime.combine(end_date, time.max), byweekday=(MO, TU, WE, TH, FR)),
            rrule(DAILY, dtstart=datetime.combine(start_date, time.min), until=datetime.combine(end_date, time.max), byweekday=(SA, SU))
        ]

        for rule in rules:
            for day_dt in rule:
                day = day_dt.date()
                is_weekend = day.weekday() >= 5
                start_h, end_h = (9, 22) if is_weekend else (7, 23)

                current = datetime.combine(day, time(start_h, 0)).replace(tzinfo=moscow_tz)
                limit_time = datetime.combine(day, time(end_h, 0)).replace(tzinfo=moscow_tz)

                while current + timedelta(minutes=interval) <= limit_time:
                    end_slot = current + timedelta(minutes=interval)

                    start_utc = current.astimezone(UTC).replace(tzinfo=None)
                    end_utc = end_slot.astimezone(UTC).replace(tzinfo=None)

                    # Пропускаем слоты в прошлом
                    if current < now_moscow:
                        current = end_slot
                        continue

                    # Проверка пересечения
                    overlap_stmt = select(TimeSlot).where(
                        TimeSlot.trainer_profile_id == profile.id,
                        TimeSlot.start_time < end_utc,
                        TimeSlot.end_time > start_utc
                    ).limit(1)
                    overlap = await session.execute(overlap_stmt)

                    if overlap.scalar():
                        current = end_slot
                        continue

                    slot = TimeSlot(
                        trainer_profile_id=profile.id,
                        start_time=start_utc,
                        end_time=end_utc,
                        format="hybrid",
                        price=default_price,
                        status="free"
                    )
                    session.add(slot)
                    await session.flush()
                    count += 1
                    current = end_slot

        await session.commit()
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

        # Get templates and trainer config
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

        now = datetime.now()
        stmt = select(TimeSlot).where(
            TimeSlot.trainer_profile_id == profile.id,
            TimeSlot.start_time >= now
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        if not slots:
            await callback.message.answer("Нет слотов для удаления.")
            return

        kb = []
        for s in slots:
            btn_text = f"❌ {s.start_time.strftime('%d.%m %H:%M')} ({int(s.price)}₽)"
            kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"slot_del_conf_{s.id}")])

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
    async with SessionLocal() as session:
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль не найден!")
            return

        await session.execute(delete(TimeSlot).where(TimeSlot.id == slot_id, TimeSlot.trainer_profile_id == profile.id))
        await session.commit()
    await callback.answer("Слот удалён.")
    # Refresh the deletion view
    await delete_slot_callback(callback, effective_user_id=effective_user_id)

@router.callback_query(F.data == "sche_config_duration")
async def config_duration_start(callback: types.CallbackQuery, state: FSMContext):
    text = "Введите стандартную длительность занятия в минутах (например, 60 или 90):"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await state.set_state("waiting_for_duration")
    await callback.answer()

@router.message(F.text, F.state == "waiting_for_duration")
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
        await message.answer(f"Длительность занятия установлена: {duration} мин.")
        await state.clear()
    except ValueError:
        await message.answer("Введите число.")

@router.callback_query(F.data == "sche_back")
async def sche_back(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    await show_schedule_menu(callback.message, is_admin=is_admin, effective_user_id=effective_user_id)
    await callback.answer()
