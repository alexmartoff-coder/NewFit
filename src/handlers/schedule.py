from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete, and_
from src.models.models import User, TimeSlot, TrainerSchedule, ScheduleTemplate, WorkFormat
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from datetime import datetime, timedelta, time
import logging

router = Router()
logger = logging.getLogger(__name__)

class ScheduleState(StatesGroup):
    choosing_date = State()
    choosing_time = State()
    choosing_duration = State()
    choosing_format = State()
    choosing_price = State()

class TemplateState(StatesGroup):
    choosing_days = State()
    choosing_start_time = State()
    choosing_end_time = State()

@router.message(F.text == "📅 Моё расписание")
@router.message(F.text == "/schedule")
async def show_schedule_menu(message: types.Message, is_admin: bool = False, effective_user_id: int = None):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📅 Посмотреть слоты", callback_data="sche_view")],
            [types.InlineKeyboardButton(text="➕ Создать новый слот", callback_data="sche_add")],
            [types.InlineKeyboardButton(text="🔁 Повторяющееся расписание", callback_data="sche_template_menu")],
            [types.InlineKeyboardButton(text="⚡ Сгенерировать из шаблонов", callback_data="sche_generate")],
            [types.InlineKeyboardButton(text="🚫 Заблокировать время", callback_data="sche_block")],
            [types.InlineKeyboardButton(text="🗑 Удалить слот", callback_data="sche_view_del")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer("Управление вашим расписанием:", reply_markup=kb)

@router.callback_query(F.data == "sche_view")
async def view_slots(callback: types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
        now = datetime.now()
        # Fetch slots for the next 14 days
        end_view = now + timedelta(days=14)
        stmt = select(TimeSlot).where(
            TimeSlot.trainer_id == user_id,
            TimeSlot.start_time >= now,
            TimeSlot.start_time <= end_view
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        kb_back = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]]
        )
        kb_back = add_admin_button(kb_back, is_admin=is_admin)

        if not slots:
            await callback.message.edit_text("📭 У вас пока нет запланированных слотов на ближайшие 14 дней.", reply_markup=kb_back)
            return

        # Group by date for better summary
        from collections import defaultdict
        grouped = defaultdict(list)
        for s in slots:
            grouped[s.start_time.date()].append(s)

        text = "📅 **Ваше расписание на 14 дней:**\n\n"
        fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид"}
        for date, day_slots in sorted(grouped.items()):
            text += f"🗓 `{date.strftime('%d.%m (%a)')}`\n"
            for s in day_slots:
                status_icon = "🟢" if s.status == "free" else ("🔴" if s.status == "booked" else "⚪")
                fmt_val = s.format.value if hasattr(s.format, 'value') else str(s.format)
                fmt_ru = fmt_map.get(fmt_val, fmt_val.lower())
                text += f"  {status_icon} {s.start_time.strftime('%H:%M')}—{s.end_time.strftime('%H:%M')} | {int(s.price)}₽ ({fmt_ru})\n"
            text += "\n"

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
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        if date_obj < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
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
        start_time = date_obj.replace(hour=time_obj.hour, minute=time_obj.minute)

        if start_time < datetime.now():
            await message.answer("Время не может быть в прошлом.")
            return

        await state.update_data(start_time_dt=start_time.isoformat())

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
    await callback.message.edit_text("Выберите формат для этого слота:", reply_markup=kb)
    await state.set_state(ScheduleState.choosing_format)
    await callback.answer()

@router.callback_query(F.data.startswith("as_fmt_"), ScheduleState.choosing_format)
async def add_slot_format(callback: types.CallbackQuery, state: FSMContext):
    fmt = callback.data.split("_")[2]
    await state.update_data(format=fmt)
    await callback.message.answer("Введите цену для этого занятия (в ₽):")
    await state.set_state(ScheduleState.choosing_price)
    await callback.answer()

@router.message(ScheduleState.choosing_price)
async def add_slot_price(message: types.Message, state: FSMContext, effective_user_id: int = None):
    try:
        price = float(message.text)
        data = await state.get_data()
        start_time = datetime.fromisoformat(data['start_time_dt'])
        duration = data['duration']
        end_time = start_time + timedelta(minutes=duration)
        user_id = effective_user_id or message.from_user.id

        async with SessionLocal() as session:
            # Check for overlaps
            stmt_overlap = select(TimeSlot).where(
                TimeSlot.trainer_id == user_id,
                and_(
                    TimeSlot.start_time < end_time,
                    TimeSlot.end_time > start_time
                )
            )
            overlap_res = await session.execute(stmt_overlap)
            if overlap_res.scalar():
                await message.answer("❌ Ошибка: В это время у вас уже есть другой слот!")
                await state.clear()
                return

            new_slot = TimeSlot(
                trainer_id=user_id,
                start_time=start_time,
                end_time=end_time,
                status="free",
                format=data['format'],
                price=price
            )
            session.add(new_slot)
            await session.commit()

        await message.answer(f"✅ Слот на {start_time.strftime('%d.%m.%Y %H:%M')} ({duration} мин) успешно добавлен!")
        await state.clear()
    except ValueError:
        await message.answer("Введите число (цена).")

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
            stmt = select(TimeSlot).where(TimeSlot.trainer_id == user_id, TimeSlot.start_time == dt)
            res = await session.execute(stmt)
            slot = res.scalar_one_or_none()

            if not slot:
                # Create a blocked slot if it doesn't exist
                slot = TimeSlot(
                    trainer_id=user_id,
                    start_time=dt,
                    end_time=dt + timedelta(minutes=60),
                    status="blocked"
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
    await callback.message.edit_text("Выберите день недели:", reply_markup=kb)
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

@router.callback_query(F.data == "sche_generate")
async def generate_slots_handler(callback: types.CallbackQuery, effective_user_id: int = None):
    trainer_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
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
        default_price = profile.price_single if profile else 0.0
        default_format = profile.work_format if profile else WorkFormat.HYBRID

        # Generate for next 14 days
        count = 0
        now = datetime.now()
        start_date = now.date()
        for i in range(14):
            current_date = start_date + timedelta(days=i)
            day_of_week = current_date.weekday()

            for t in templates:
                if t.day_of_week == day_of_week:
                    sh, sm = map(int, t.start_time.split(':'))
                    eh, em = map(int, t.end_time.split(':'))

                    template_start = datetime.combine(current_date, time(sh, sm))
                    template_end = datetime.combine(current_date, time(eh, em))

                    # Split template interval into slots
                    current_slot_start = template_start
                    while current_slot_start + timedelta(minutes=slot_duration) <= template_end:
                        current_slot_end = current_slot_start + timedelta(minutes=slot_duration)

                        if current_slot_start > now:
                            # Check for overlaps (more robust than exact start check)
                            check_stmt = select(TimeSlot).where(
                                TimeSlot.trainer_id == trainer_id,
                                and_(
                                    TimeSlot.start_time < current_slot_end,
                                    TimeSlot.end_time > current_slot_start
                                )
                            )
                            exists = await session.execute(check_stmt)
                            if not exists.scalar():
                                new_slot = TimeSlot(
                                    trainer_id=trainer_id,
                                    start_time=current_slot_start,
                                    end_time=current_slot_end,
                                    status="free",
                                    format=default_format,
                                    price=default_price
                                )
                                session.add(new_slot)
                                count += 1

                        current_slot_start = current_slot_end

        await session.commit()
    await callback.message.answer(f"✅ Генерация завершена. Добавлено слотов: {count} (длительность {slot_duration} мин, цена {default_price}₽)")
    await callback.answer()

@router.callback_query(F.data == "sche_view_del")
async def delete_slot_callback(callback: types.CallbackQuery, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    # For simplicity, we just list slots and allow deletion
    async with SessionLocal() as session:
        now = datetime.now()
        stmt = select(TimeSlot).where(
            TimeSlot.trainer_id == user_id,
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
        await callback.message.edit_text("Выберите слот для удаления:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data.startswith("slot_del_conf_"))
async def process_slot_deletion(callback: types.CallbackQuery, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    slot_id = int(callback.data.split("_")[3])
    async with SessionLocal() as session:
        await session.execute(delete(TimeSlot).where(TimeSlot.id == slot_id, TimeSlot.trainer_id == user_id))
        await session.commit()
    await callback.answer("Слот удалён.")
    # Refresh the deletion view
    await delete_slot_callback(callback, effective_user_id=effective_user_id)

@router.callback_query(F.data == "sche_config_duration")
async def config_duration_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите стандартную длительность занятия в минутах (например, 60 или 90):")
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
