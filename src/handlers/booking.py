from aiogram import Router, types, F, exceptions
from aiogram.fsm.context import FSMContext
from src.states.booking import BookingSession
from src.services.calendar import CalendarService
from src.services.payments import PaymentService
from src.models.models import TrainerProfile, User, ClientProfile, TimeSlot, Booking, UserRole
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone
import logging

router = Router()
logger = logging.getLogger(__name__)
from src.utils.text import escape_md

@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    trainer_user_id = int(callback.data.split("_")[1])

    # Resolve professional profile
    async with SessionLocal() as session:
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == trainer_user_id).options(selectinload(TrainerProfile.specializations))
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль профессионала не найден!")
            return

        trainer_profile_id = profile.id
        # Store specialist's services in state for terminology/format fix later
        specs = [s.name for s in profile.specializations]
        await state.update_data(trainer_profile_id=trainer_profile_id, trainer_user_id=trainer_user_id, specializations=specs)

        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        end_view_utc = now_utc + timedelta(days=30)

        stmt = select(TimeSlot.start_time).where(
            TimeSlot.trainer_profile_id == trainer_profile_id,
            TimeSlot.status == "free",
            TimeSlot.start_time >= now_utc,
            TimeSlot.start_time <= end_view_utc
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)

        # Extract unique dates in Moscow time
        available_dates = []
        seen_dates = set()
        for ts_start in res.scalars():
            # ts_start is naive UTC from DB
            dt_msk = ts_start.replace(tzinfo=UTC).astimezone(moscow_tz)
            date_msk = dt_msk.date()
            if date_msk not in seen_dates:
                available_dates.append(date_msk)
                seen_dates.add(date_msk)

        if not available_dates:
            text = "К сожалению, у этого профессионала нет свободных слотов на ближайшее время."
            if callback.message.photo:
                await callback.message.edit_caption(caption=text)
            else:
                await callback.message.edit_text(text)
            await callback.answer()
            return

        days_ru = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
        kb = []
        row = []
        for d in available_dates:
            day_name = days_ru.get(d.weekday(), "")
            row.append(types.InlineKeyboardButton(
                text=f"{d.strftime('%d.%m')} ({day_name})",
                callback_data=f"bdate_{d.isoformat()}"
            ))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        kb.append([types.InlineKeyboardButton(text="🔙 Назад в каталог", callback_data="filter_apply")])

    kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    kb_markup = add_admin_button(kb_markup, is_admin=is_admin)

    # Resolve professional name for the header
    async with SessionLocal() as session:
        trainer_user = await session.get(User, trainer_user_id)
        trainer_name = trainer_user.full_name if trainer_user else "Мастер"

    text = f"Мастер: {escape_md(trainer_name)}\n\nВыберите дату для записи:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb_markup)
    else:
        await callback.message.edit_text(text, reply_markup=kb_markup)
    await callback.answer()

@router.callback_query(F.data.startswith("bdate_"))
async def booking_date_selected(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    selected_date_str = callback.data.split("_")[1]
    selected_date = datetime.fromisoformat(selected_date_str).date()
    data = await state.get_data()
    trainer_profile_id = data['trainer_profile_id']
    trainer_user_id = data['trainer_user_id']

    # Initialize and keep selected_slots in FSM state
    selected_slots = data.get('selected_slots', [])
    await state.update_data(selected_date=selected_date_str, selected_slots=selected_slots)

    async with SessionLocal() as session:
        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')

        # Convert Moscow date range to UTC for DB query
        start_msk = datetime.combine(selected_date, datetime.min.time()).replace(tzinfo=moscow_tz)
        end_msk = datetime.combine(selected_date, datetime.max.time()).replace(tzinfo=moscow_tz)

        start_utc = start_msk.astimezone(UTC).replace(tzinfo=None)
        end_utc = end_msk.astimezone(UTC).replace(tzinfo=None)

        # Filter out slots that have already started
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        effective_start_utc = max(start_utc, now_utc)

        stmt = select(TimeSlot).where(
            TimeSlot.trainer_profile_id == trainer_profile_id,
            TimeSlot.status == "free",
            TimeSlot.start_time >= effective_start_utc,
            TimeSlot.start_time <= end_utc
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        if not slots:
            text = "На этот день нет свободных слотов. Выберите другую дату."
            if callback.message.photo:
                await callback.message.edit_caption(caption=text)
            else:
                await callback.message.edit_text(text)
            await callback.answer()
            return

        kb = []
        row = []
        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')

        for s in slots:
            # Ensure MSK conversion for button labels
            s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
            s_end = s.end_time.replace(tzinfo=UTC) if s.end_time.tzinfo is None else s.end_time.astimezone(UTC)

            start_str = s_start.astimezone(moscow_tz).strftime('%H:%M')
            end_str = s_end.astimezone(moscow_tz).strftime('%H:%M')

            # Render tick checkmark if selected
            is_selected = s.id in selected_slots
            tick_mark = "✅ " if is_selected else ""
            btn_text = f"{tick_mark}{start_str}-{end_str}"
            row.append(types.InlineKeyboardButton(text=btn_text, callback_data=f"tslot_toggle_{s.id}"))
            if len(row) == 3:
                kb.append(row)
                row = []

        if row:
            kb.append(row)

        # Primary "Забронировать время" button if at least one is selected
        if selected_slots:
            kb.append([types.InlineKeyboardButton(text="Забронировать время", callback_data="tslot_confirm")])

        kb.append([types.InlineKeyboardButton(text="🔙 К выбору даты", callback_data=f"book_{trainer_user_id}")])
        kb.append([types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="client_menu")])
        kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        kb_markup = add_admin_button(kb_markup, is_admin=is_admin)

        # Resolve professional name for the header
        trainer_user = await session.get(User, trainer_user_id)
        trainer_name = trainer_user.full_name if trainer_user else "Мастер"

        text = f"Мастер: {escape_md(trainer_name)}\n\nСвободные слоты на {selected_date.strftime('%d.%m')}:\n*(Вы можете выбрать несколько слотов)*"
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb_markup, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text, reply_markup=kb_markup, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("tslot_toggle_"))
async def process_slot_toggle(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    slot_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected_slots = data.get('selected_slots', [])

    if slot_id in selected_slots:
        selected_slots.remove(slot_id)
    else:
        selected_slots.append(slot_id)

    await state.update_data(selected_slots=selected_slots)

    # Re-render the slot selection keyboard for the current date
    selected_date_str = data.get('selected_date')
    callback.data = f"bdate_{selected_date_str}"
    await booking_date_selected(callback, state, is_admin=is_admin)

@router.callback_query(F.data == "tslot_confirm")
async def process_multi_slot_confirm(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    data = await state.get_data()
    selected_slots = data.get('selected_slots', [])
    trainer_user_id = data.get('trainer_user_id')
    trainer_profile_id = data.get('trainer_profile_id')

    if not selected_slots:
        await callback.answer("Выберите хотя бы один временной слот!", show_alert=True)
        return

    # Store the first slot ID for backward compatibility with existing single-slot handlers
    await state.update_data(slot_id=selected_slots[0])

    async with SessionLocal() as session:
        # Load slots details for validation and ordering
        stmt = select(TimeSlot).where(TimeSlot.id.in_(selected_slots)).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        # Verify slots are still free
        for s in slots:
            if s.status != "free" or s.start_time < now_utc:
                await callback.answer(f"Слот на {s.start_time.strftime('%H:%M')} уже занят или недоступен. Пожалуйста, выберите другие.", show_alert=True)
                return

        # Fetch trainer role + specializations
        stmt_p = select(TrainerProfile).where(TrainerProfile.id == trainer_profile_id).options(
            selectinload(TrainerProfile.specializations),
            selectinload(TrainerProfile.user)
        )
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль профессионала не найден!")
            return

        # Store selected specs and details
        spec_names = [s.name for s in profile.specializations]
        await state.update_data(specializations=spec_names)

        trainer_role = profile.user.role
        specs = profile.specializations
        if specs:
            # Step 1: Choose Service (if applicable)
            await state.set_state(BookingSession.choosing_service)
            kb = []
            row = []
            for i, s in enumerate(specs):
                row.append(types.InlineKeyboardButton(text=s.name, callback_data=f"c_svc_{i}"))
                if len(row) == 2:
                    kb.append(row)
                    row = []
            if row:
                kb.append(row)

            selected_date_str = data.get('selected_date')
            kb.append([types.InlineKeyboardButton(text="🔙 К выбору времени", callback_data=f"bdate_{selected_date_str}")])

            term = "услугу" if trainer_role in [UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL] else "направление"

            # Determine price info
            total_price = sum(s.price for s in slots)
            price_text = f"Общая цена: `{int(total_price)}₽`"

            # Format selected times for the message
            from dateutil.tz import gettz, UTC
            moscow_tz = gettz('Europe/Moscow')
            time_strings = []
            for s in slots:
                s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
                time_strings.append(s_start.astimezone(moscow_tz).strftime('%H:%M'))
            times_formatted = ", ".join(time_strings)

            text = (
                f"👤 Мастер: {escape_md(profile.user.full_name)}\n"
                f"⏰ Выбранное время: `{times_formatted}`\n"
                f"💰 {price_text}\n\n"
                f"Выберите {term} для записи:"
            )
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
            else:
                await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
            return

        # No specs, proceed directly to confirmation
        await proceed_to_format_selection_or_confirm(callback, state, slots[0], is_admin)

@router.callback_query(F.data.startswith("slot_") & ~F.data.startswith("slot_confirm_"))
async def process_slot_selection(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    # This handler now shows a detailed preview of the slot
    slot_id = int(callback.data.split("_")[1])

    async with SessionLocal() as session:
        # Load slot and trainer
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user)
            )
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if not slot or slot.status != "free" or slot.start_time < now_utc:
            text = "Этот слот уже занят или недоступен. Выберите другой."
            if callback.message.photo:
                await callback.message.edit_caption(caption=text)
            else:
                await callback.message.edit_text(text)
            return

        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')
        s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
        s_end = slot.end_time.replace(tzinfo=UTC) if slot.end_time.tzinfo is None else slot.end_time.astimezone(UTC)
        start_moscow = s_start.astimezone(moscow_tz)
        end_moscow = s_end.astimezone(moscow_tz)

        fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид", "offline": "оффлайн", "online": "онлайн", "hybrid": "гибрид"}
        fmt_text = fmt_map.get(slot.format, slot.format)

        # Acknowledge the callback silently.
        # The slot details are displayed via message editing below (popover behavior).
        await callback.answer()

        details = (
            f"📅 *Забронировать время: {start_moscow.strftime('%d.%m.%Y')}*\n"
            f"👤 Мастер: {escape_md(slot.trainer_profile.user.full_name)}\n"
            f"⏰ {start_moscow.strftime('%H:%M')}—{end_moscow.strftime('%H:%M')}\n"
            f"📍 {fmt_text}\n"
            f"💰 Цена: {int(slot.price)}₽\n"
        )

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="Забронировать время", callback_data=f"slot_confirm_{slot.id}")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"bdate_{slot.start_time.date().isoformat()}")]
        ])

        if callback.message.photo:
            await callback.message.edit_caption(caption=details, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text=details, reply_markup=kb, parse_mode="Markdown")

    await callback.answer()

@router.callback_query(F.data.startswith("slot_confirm_"))
async def process_slot_selection_confirmed(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    slot_id = int(callback.data.split("_")[2])

    async with SessionLocal() as session:
        # Load slot and trainer role + specializations
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user),
                selectinload(TrainerProfile.specializations)
            )
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        if not slot or slot.status != "free" or slot.start_time < now_utc:
            text = "Этот слот уже занят или недоступен."
            await callback.answer(text, show_alert=True)
            return

        # Store specialist's services in state for terminology/format fix later
        spec_names = [s.name for s in slot.trainer_profile.specializations]
        await state.update_data(slot_id=slot_id, start_time=slot.start_time.isoformat(), specializations=spec_names)

        # Step 1: Choose Service (if applicable)
        trainer_role = slot.trainer_profile.user.role
        specs = slot.trainer_profile.specializations
        if specs:
            await state.set_state(BookingSession.choosing_service)
            kb = []
            row = []
            for i, s in enumerate(specs):
                # Use index to avoid callback data length issues
                row.append(types.InlineKeyboardButton(text=s.name, callback_data=f"c_svc_{i}"))
                if len(row) == 2:
                    kb.append(row)
                    row = []
            if row:
                kb.append(row)
            kb.append([types.InlineKeyboardButton(text="🔙 К выбору времени", callback_data=f"bdate_{slot.start_time.date().isoformat()}")])

            term = "услугу" if trainer_role in [UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL] else "направление"

            # Use "from X" price if services have individual pricing
            price_text = f"Цена: `{int(slot.price)}₽`"
            if slot.trainer_profile.service_prices:
                min_price = min(slot.trainer_profile.service_prices.values())
                price_text = f"Цена: от `{int(min_price)}₽`"

            from dateutil.tz import gettz, UTC
            moscow_tz = gettz('Europe/Moscow')
            s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
            start_moscow = s_start.astimezone(moscow_tz)

            trainer_name = slot.trainer_profile.user.full_name
            text = (
                f"👤 Мастер: {escape_md(trainer_name)}\n"
                f"⏰ Время: `{start_moscow.strftime('%d.%m %H:%M')}`\n"
                f"{price_text}\n\n"
                f"Выберите {term} для записи:"
            )
            if callback.message.photo:
                await callback.message.edit_caption(caption=text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
            else:
                await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
            return

        await proceed_to_format_selection_or_confirm(callback, state, slot, is_admin)
    await callback.answer()

@router.callback_query(F.data.startswith("c_svc_"), BookingSession.choosing_service)
async def process_service_selection(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    try:
        idx = int(callback.data.replace("c_svc_", ""))
    except ValueError:
        await callback.answer("Неверный формат данных.")
        return

    data = await state.get_data()
    specs = data.get('specializations', [])

    if 0 <= idx < len(specs):
        svc_name = specs[idx]
        await state.update_data(selected_service=svc_name)
    else:
        await callback.answer("Услуга не найдена.")
        return

    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == data['slot_id']).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user)
            )
        )
        slot = (await session.execute(stmt)).scalar_one_or_none()

        # Look up price for the selected service
        price_found = None
        if slot and slot.trainer_profile.service_prices:
            price_found = slot.trainer_profile.service_prices.get(svc_name)
            if price_found is not None:
                await state.update_data(override_price=float(price_found))

        await proceed_to_format_selection_or_confirm(callback, state, slot, is_admin)
    await callback.answer()

async def proceed_to_format_selection_or_confirm(callback: types.CallbackQuery, state: FSMContext, slot: TimeSlot, is_admin: bool):
    # Bypassed format selection completely: force OFFLINE mode
    await state.update_data(override_format="OFFLINE")
    await show_booking_confirmation(callback, state, slot, is_admin)

@router.callback_query(F.data.startswith("c_fmt_"), BookingSession.choosing_format)
async def process_format_selection(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    fmt_choice = callback.data.split("_")[2]
    fmt_map = {"offline": "OFFLINE", "online": "ONLINE"}
    chosen_fmt = fmt_map.get(fmt_choice, "OFFLINE")
    await state.update_data(override_format=chosen_fmt)

    data = await state.get_data()
    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == data['slot_id']).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user)
            )
        )
        slot = (await session.execute(stmt)).scalar_one_or_none()

        # If ONLINE chosen, check for specialist's online price
        if chosen_fmt == "ONLINE" and slot and slot.trainer_profile.price_online > 0:
            # Service price from Step 1 usually takes precedence if present
            if 'override_price' not in data:
                await state.update_data(override_price=slot.trainer_profile.price_online)

        await show_booking_confirmation(callback, state, slot, is_admin)
    await callback.answer()

async def show_booking_confirmation(callback: types.CallbackQuery, state: FSMContext, slot: TimeSlot, is_admin: bool):
    await state.set_state(BookingSession.confirming_booking)

    from dateutil.tz import gettz, UTC
    moscow_tz = gettz('Europe/Moscow')
    s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)

    # Dynamic terminology based on specialist role
    data = await state.get_data()
    specs = data.get('specializations', [])
    selected_slots = data.get('selected_slots', [slot.id])

    # Determine if we should use 'Услуга' label
    is_beauty = slot.trainer_profile.user.role == UserRole.BEAUTY

    is_specific_sport = any(s in ["Большой теннис", "Падл"] for s in specs)
    is_service_based = is_beauty or is_specific_sport

    term_format = "Услуга" if is_service_based else "Формат"

    # Use the selected format/service from state if present
    selected_svc = data.get('selected_service', '')
    chosen_fmt = data.get('override_format', '')

    fmt_ru_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид", "offline": "оффлайн", "online": "онлайн", "hybrid": "гибрид"}

    display_format = selected_svc
    if chosen_fmt:
        if display_format:
            display_format += f" ({fmt_ru_map.get(chosen_fmt, chosen_fmt)})"
        else:
            display_format = fmt_ru_map.get(chosen_fmt, chosen_fmt)

    if not display_format:
        display_format = fmt_ru_map.get(slot.format, slot.format)

    selected_date = s_start.date().isoformat()
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Забронировать время", callback_data="confirm_booking")],
            [types.InlineKeyboardButton(text="🔙 К выбору времени", callback_data=f"bdate_{selected_date}")],
            [types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="client_menu")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)

    # Load all selected slots to format times and sum prices
    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id.in_(selected_slots)).order_by(TimeSlot.start_time.asc())
        slots = (await session.execute(stmt)).scalars().all()

    time_strings = []
    total_price = 0.0
    for s in slots:
        start_utc = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
        time_strings.append(start_utc.astimezone(moscow_tz).strftime('%H:%M'))
        total_price += data.get('override_price', s.price)

    times_formatted = ", ".join(time_strings)
    date_formatted = s_start.astimezone(moscow_tz).strftime('%d.%m.%Y')

    trainer_name = slot.trainer_profile.user.full_name
    text = (
        f"📍 *Подтверждение записи*\n\n"
        f"👤 Мастер: {escape_md(trainer_name)}\n"
        f"📅 Дата: `{date_formatted}`\n"
        f"⏰ Время: `{times_formatted}` (МСК)\n"
        f"🏷 {term_format}: `{escape_md(display_format)}`\n"
        f"💰 Общая цена: `{int(total_price)}₽`\n\n"
        f"Нажмите подтвердить для завершения записи."
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "confirm_booking", BookingSession.confirming_booking)
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    data = await state.get_data()
    selected_slots = data.get('selected_slots', [data['slot_id']])
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        # Safety check: ensure client user exists in 'users' table
        client_user = await session.get(User, user_id)
        if not client_user:
            client_user = User(
                id=user_id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name or f"User {user_id}",
                role=UserRole.CLIENT
            )
            session.add(client_user)
            await session.flush()

        stmt_cp = select(ClientProfile).where(ClientProfile.user_id == user_id)
        res_cp = await session.execute(stmt_cp)
        client_profile = res_cp.scalar_one_or_none()

        if not client_profile:
            client_profile = ClientProfile(
                user_id=user_id,
                full_name=client_user.full_name,
                status="active"
            )
            session.add(client_profile)
            await session.flush()

        # Load all selected slots with relationship loading
        stmt = select(TimeSlot).where(TimeSlot.id.in_(selected_slots)).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user)
            )
        ).order_by(TimeSlot.start_time.asc())
        slots = (await session.execute(stmt)).scalars().all()

        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        # Verify slots are still free
        for slot in slots:
            if not slot or slot.status != "free" or slot.start_time < now_utc:
                text = "Один или несколько выбранных слотов уже заняты или недоступны."
                await callback.answer(text, show_alert=True)
                return

        # Pre-fetch all necessary attributes before commit to avoid MissingGreenlet
        client_name = client_profile.full_name
        trainer_name = slots[0].trainer_profile.user.full_name
        trainer_user_id = slots[0].trainer_profile.user_id

        # Build full slot format string (Service + Format)
        selected_svc = data.get('selected_service', '')
        chosen_fmt = data.get('override_format', 'OFFLINE')
        fmt_ru_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид", "offline": "оффлайн", "online": "онлайн", "hybrid": "гибрид"}

        slot_format = selected_svc
        if chosen_fmt:
            if slot_format:
                slot_format += f" ({fmt_ru_map.get(chosen_fmt, chosen_fmt)})"
            else:
                slot_format = fmt_ru_map.get(chosen_fmt, chosen_fmt)

        if not slot_format:
            slot_format = slots[0].format

        is_beauty = slots[0].trainer_profile.user.role == UserRole.BEAUTY
        is_specific_sport = any(s in ["Большой теннис", "Падл"] for s in slot_format.split(", "))

        term_lesson = "на услугу" if (is_beauty or is_specific_sport) else "на тренировку"
        term_format = "Услуга" if (is_beauty or is_specific_sport) else "Формат"

        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')

        booked_time_details = []
        total_price = 0.0

        # Loop and book all slots
        for slot in slots:
            slot_start = slot.start_time
            slot_end = slot.end_time
            slot_price = data.get('override_price', slot.price)

            slot.status = "booked"
            slot.client_id = user_id
            slot.format = slot_format
            slot.price = slot_price

            new_booking = Booking(
                slot_id=slot.id,
                trainer_profile_id=slot.trainer_profile_id,
                client_id=client_profile.id,
                start_time=slot_start,
                end_time=slot_end,
                status="confirmed",
                price=slot_price,
                paid=False
            )
            session.add(new_booking)
            await session.flush()

            # Reminders
            from src.services.reminders import ReminderService
            is_online = ("онлайн" in slot_format.lower() or "online" in slot_format.lower())
            await ReminderService.schedule_reminders(session, new_booking.id, user_id, trainer_user_id, slot_start, slot_end, is_online=is_online)

            # Sync to Google Calendar
            try:
                from src.services.calendar import CalendarService
                await CalendarService.add_event_to_google(trainer_user_id, new_booking.id)
            except Exception as e:
                logger.error(f"Failed to sync with Google Calendar for trainer {trainer_user_id}: {e}")

            s_start = slot_start.replace(tzinfo=UTC) if slot_start.tzinfo is None else slot_start.astimezone(UTC)
            start_moscow = s_start.astimezone(moscow_tz)
            booked_time_details.append(f"⏰ `{start_moscow.strftime('%d.%m.%Y %H:%M')}`")
            total_price += slot_price

        await session.commit()

        # Format confirmation messages
        times_formatted_msg = "\n".join(booked_time_details)
        text = f"✅ *Запись успешно подтверждена!*\n\nВы успешно записаны {term_lesson} к мастеру {escape_md(trainer_name)}.\n\nВыбранное время:\n{times_formatted_msg}\n\n📅 Мы пришлем вам напоминание за 24 и 2 часа до начала."

        # Show main menu keyboard to client
        from src.keyboards.common import get_client_main_kb
        stmt_t = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        has_trainer_profile = (await session.execute(stmt_t)).scalar_one_or_none() is not None
        kb = get_client_main_kb(has_specialists=True, is_pro=has_trainer_profile)

        # Cleanup confirmation screen
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        # Send final confirmation message
        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=text,
            reply_markup=kb,
            parse_mode="Markdown"
        )

        # Notify professional
        try:
            trainer_text = (
                f"🆕 *Новая запись!*\n\n"
                f"👤 Клиент: {escape_md(client_name)}\n"
                f"📅 Выбранное время:\n"
            )
            for slot in slots:
                s_start_slot = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
                start_moscow_slot = s_start_slot.astimezone(moscow_tz)
                trainer_text += f" • {start_moscow_slot.strftime('%d.%m %H:%M')}\n"

            trainer_text += (
                f"\n🏷 {term_format}: {escape_md(slot_format)}\n"
                f"💰 Общая цена: {int(total_price)}₽"
            )
            await callback.bot.send_message(trainer_user_id, trainer_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify professional {trainer_user_id}: {e}")
        else:
            text = "К сожалению, этот слот уже занят или недоступен."
            if callback.message.photo:
                await callback.message.edit_caption(caption=text)
            else:
                await callback.message.edit_text(text)

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_booking", BookingSession.confirming_booking)
async def cancel_booking(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text = "Запись отменена."
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await callback.answer()
