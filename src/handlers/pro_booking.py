import logging
from datetime import datetime, timedelta, timezone
from dateutil.tz import gettz, UTC

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.models.models import User, TrainerProfile, ClientProfile, UserRole, Booking, TimeSlot
from src.utils.db import SessionLocal
from src.utils.text import escape_md
from src.states.pro_booking import ProBookingSession
from src.keyboards.inline import add_admin_button

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("pro_book_client_"))
async def pro_start_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    parts = callback.data.split("_")
    client_id = int(parts[3])
    slot_id = int(parts[4]) if len(parts) > 4 else None

    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        # Get professional profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль не найден", show_alert=True)
            return

        # Get client profile to show name
        client = await session.get(ClientProfile, client_id)
        if not client:
            await callback.answer("Клиент не найден", show_alert=True)
            return

        await state.update_data(client_id=client_id, trainer_profile_id=profile.id, client_name=client.full_name)

        if slot_id:
            await state.update_data(slot_id=slot_id)
            # Re-fetch slot for jumping
            stmt_s = select(TimeSlot).where(TimeSlot.id == slot_id).options(
                selectinload(TimeSlot.trainer_profile).options(
                    selectinload(TrainerProfile.user),
                    selectinload(TrainerProfile.specializations)
                )
            )
            slot = (await session.execute(stmt_s)).scalar_one_or_none()
            if slot and slot.status == "free":
                # Jump straight to service selection
                specs = slot.trainer_profile.specializations
                if specs:
                    await state.set_state(ProBookingSession.choosing_service)
                    kb = []
                    for i, spec in enumerate(specs):
                        kb.append([types.InlineKeyboardButton(text=spec.name, callback_data=f"pro_svc_{i}")])
                    kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="clients_list")])

                    role = slot.trainer_profile.user.role
                    term = "услугу" if role in [UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL] else "направление"

                    price_text = f"Цена: `{int(slot.price)}₽`"
                    if slot.trainer_profile.service_prices:
                        min_price = min(slot.trainer_profile.service_prices.values())
                        price_text = f"Цена: от `{int(min_price)}₽`"

                    from dateutil.tz import gettz, UTC
                    moscow_tz = gettz('Europe/Moscow')
                    s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
                    start_moscow = s_start.astimezone(moscow_tz)

                    text = (
                        f"👤 Клиент: **{escape_md(client.full_name)}**\n"
                        f"⏰ Время: `{start_moscow.strftime('%d.%m %H:%M')}`\n"
                        f"{price_text}\n\n"
                        f"Выберите {term} для этой записи:"
                    )
                    kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
                    if callback.message.photo:
                        await callback.message.edit_caption(caption=text, reply_markup=kb_markup, parse_mode="Markdown")
                    else:
                        await callback.message.edit_text(text, reply_markup=kb_markup, parse_mode="Markdown")
                    return
                else:
                    await proceed_to_format_or_confirm(callback, state, slot)
                    return

        # Find available dates
        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        end_view_utc = now_utc + timedelta(days=30)

        stmt = select(TimeSlot.start_time).where(
            TimeSlot.trainer_profile_id == profile.id,
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
            text = "У вас нет свободных слотов в расписании. Сначала добавьте слоты."
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
                callback_data=f"pro_bdate_{d.isoformat()}"
            ))
            if len(row) == 2:
                kb.append(row)
                row = []
        if row:
            kb.append(row)
        kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="clients_list")]) # To be handled by show_clients

    await state.set_state(ProBookingSession.choosing_date)
    text = f"Клиент: **{escape_md(client.full_name)}**\n\nВыберите дату для записи:"
    kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb_markup, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=kb_markup, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("pro_bdate_"), ProBookingSession.choosing_date)
async def pro_date_selected(callback: types.CallbackQuery, state: FSMContext):
    selected_date = datetime.fromisoformat(callback.data.split("_")[-1]).date()
    data = await state.get_data()
    trainer_profile_id = data['trainer_profile_id']

    async with SessionLocal() as session:
        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')

        # Convert Moscow date range to UTC for DB query
        start_msk = datetime.combine(selected_date, datetime.min.time()).replace(tzinfo=moscow_tz)
        end_msk = datetime.combine(selected_date, datetime.max.time()).replace(tzinfo=moscow_tz)

        start_utc = start_msk.astimezone(UTC).replace(tzinfo=None)
        end_utc = end_msk.astimezone(UTC).replace(tzinfo=None)

        stmt = select(TimeSlot).where(
            TimeSlot.trainer_profile_id == trainer_profile_id,
            TimeSlot.status == "free",
            TimeSlot.start_time >= start_utc,
            TimeSlot.start_time <= end_utc
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        if not slots:
            await callback.answer("На этот день нет свободных слотов", show_alert=True)
            return

        kb = []
        row = []
        moscow_tz = gettz('Europe/Moscow')
        for s in slots:
            s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
            start_str = s_start.astimezone(moscow_tz).strftime('%H:%M')
            row.append(types.InlineKeyboardButton(text=f"{start_str}", callback_data=f"pro_slot_{s.id}"))
            if len(row) == 3:
                kb.append(row)
                row = []
        if row:
            kb.append(row)

        kb.append([types.InlineKeyboardButton(text="🔙 К выбору даты", callback_data=f"pro_book_client_{data['client_id']}")])

        await state.set_state(ProBookingSession.choosing_slot)
    text = f"Клиент: **{escape_md(data['client_name'])}**\n\nВыберите время на {selected_date.strftime('%d.%m')}:"
    kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb_markup, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=kb_markup, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("pro_slot_"), ProBookingSession.choosing_slot)
async def pro_slot_selected(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    slot_id = int(callback.data.split("_")[-1])
    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user),
                selectinload(TrainerProfile.specializations)
            )
        )
        slot = (await session.execute(stmt)).scalar_one_or_none()

        if not slot or slot.status != "free":
            await callback.answer("Слот уже занят", show_alert=True)
            return

        await state.update_data(slot_id=slot_id)

        # Step 1: Choose Service/Direction
        specs = slot.trainer_profile.specializations
        if specs:
            await state.set_state(ProBookingSession.choosing_service)
            kb = []
            for i, spec in enumerate(specs):
                kb.append([types.InlineKeyboardButton(text=spec.name, callback_data=f"pro_svc_{i}")])
            kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"pro_bdate_{slot.start_time.date().isoformat()}")])

            role = slot.trainer_profile.user.role
            term = "услугу" if role in [UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL] else "направление"

            price_text = f"Цена: `{int(slot.price)}₽`"
            if slot.trainer_profile.service_prices:
                min_price = min(slot.trainer_profile.service_prices.values())
                price_text = f"Цена: от `{int(min_price)}₽`"

            from dateutil.tz import gettz, UTC
            moscow_tz = gettz('Europe/Moscow')
            s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
            start_moscow = s_start.astimezone(moscow_tz)

            text = (
                f"👤 Клиент: **{escape_md(data['client_name'])}**\n"
                f"⏰ Время: `{start_moscow.strftime('%d.%m %H:%M')}`\n"
                f"{price_text}\n\n"
                f"Выберите {term} для этой записи:"
            )

            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
                    parse_mode="Markdown"
                )
            else:
                await callback.message.edit_text(
                    text,
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb),
                    parse_mode="Markdown"
                )
            return

        await proceed_to_format_or_confirm(callback, state, slot)
    await callback.answer()

@router.callback_query(F.data.startswith("pro_svc_"), ProBookingSession.choosing_service)
async def pro_service_selected(callback: types.CallbackQuery, state: FSMContext):
    try:
        idx = int(callback.data.replace("pro_svc_", ""))
    except ValueError:
        await callback.answer("Неверный формат данных.", show_alert=True)
        return

    data = await state.get_data()
    async with SessionLocal() as session:
        # We need the specs of this trainer.
        # Actually we can get them from the slot or state if we stored them.
        # Let's re-fetch the slot to be safe and accurate with indices.
        stmt = select(TimeSlot).where(TimeSlot.id == data['slot_id']).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.specializations)
            )
        )
        slot = (await session.execute(stmt)).scalar_one_or_none()

        if not slot:
            await callback.answer("Слот не найден.", show_alert=True)
            return

        specs = slot.trainer_profile.specializations
        if 0 <= idx < len(specs):
            service_name = specs[idx].name
            await state.update_data(selected_service=service_name)
        else:
            await callback.answer("Услуга не найдена.", show_alert=True)
            return

    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == data['slot_id']).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user)
            )
        )
        slot = (await session.execute(stmt)).scalar_one_or_none()

        price_found = None
        if slot and slot.trainer_profile.service_prices:
            price_found = slot.trainer_profile.service_prices.get(service_name)
            if price_found is not None:
                await state.update_data(override_price=float(price_found))

        display_price = price_found if price_found is not None else slot.price
        text_svc = f"Выбрана услуга: **{escape_md(service_name)}**\nЦена: `{int(display_price)}₽`\n\nПродолжаем..."
        if callback.message.photo:
            await callback.message.edit_caption(caption=text_svc, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text=text_svc, parse_mode="Markdown")

        await proceed_to_format_or_confirm(callback, state, slot)
    await callback.answer()

async def proceed_to_format_or_confirm(callback: types.CallbackQuery, state: FSMContext, slot: TimeSlot):
    # Check if we need to ask for format (offline/online)
    trainer_role = slot.trainer_profile.user.role
    if trainer_role == UserRole.TRAINER and (slot.format.lower() == "hybrid" or slot.format.lower() == "гибрид"):
        await state.set_state(ProBookingSession.choosing_format)
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🏢 Оффлайн", callback_data="pro_fmt_OFFLINE")],
            [types.InlineKeyboardButton(text="💻 Онлайн", callback_data="pro_fmt_ONLINE")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"pro_slot_{slot.id}")]
        ])

        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')
        s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
        start_moscow = s_start.astimezone(moscow_tz)
        data = await state.get_data()

        text = (
            f"👤 Клиент: **{escape_md(data['client_name'])}**\n"
            f"⏰ Время: `{start_moscow.strftime('%d.%m %H:%M')}`\n\n"
            f"Выберите формат для этой записи:"
        )

        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    await show_pro_booking_confirmation(callback, state, slot)

@router.callback_query(F.data.startswith("pro_fmt_"), ProBookingSession.choosing_format)
async def pro_format_selected(callback: types.CallbackQuery, state: FSMContext):
    fmt_choice = callback.data.split("_")[2]
    fmt_map = {"OFFLINE": "OFFLINE", "ONLINE": "ONLINE"}
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

        await show_pro_booking_confirmation(callback, state, slot)
    await callback.answer()

async def show_pro_booking_confirmation(callback: types.CallbackQuery, state: FSMContext, slot: TimeSlot):
    data = await state.get_data()
    moscow_tz = gettz('Europe/Moscow')
    s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
    start_moscow = s_start.astimezone(moscow_tz)

    # Dynamic terminology
    is_beauty = slot.trainer_profile.user.role == UserRole.BEAUTY
    is_specific_sport = any(s in ["Большой теннис", "Падл"] for s in slot.format.split(", "))
    term_format = "Услуга" if (is_beauty or is_specific_sport) else "Формат"

    display_format = data.get('selected_service', '')
    if data.get('override_format'):
        fmt_ru_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид"}
        fmt_ru = fmt_ru_map.get(data['override_format'], data['override_format'])
        if display_format:
            display_format += f" ({fmt_ru})"
        else:
            display_format = fmt_ru

    if not display_format:
        display_format = slot.format
        fmt_ru_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид"}
        display_format = fmt_ru_map.get(display_format, display_format)

    display_price = data.get('override_price', slot.price)

    text = (
        f"❓ **Подтвердите запись клиента**\n\n"
        f"👤 Клиент: {data['client_name']}\n"
        f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
        f"🏷 {term_format}: {display_format}\n"
        f"💰 Цена: {int(display_price)}₽"
    )

    kb = [
        [types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="pro_confirm_booking")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="pro_cancel")]
    ]

    await state.set_state(ProBookingSession.confirming)
    kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb_markup, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=kb_markup, parse_mode="Markdown")

@router.callback_query(F.data == "pro_confirm_booking", ProBookingSession.confirming)
async def pro_confirm_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    data = await state.get_data()
    slot_id = data['slot_id']
    client_id = data['client_id']
    pro_user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user)
            )
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        client_profile = await session.get(ClientProfile, client_id, options=[selectinload(ClientProfile.user)])

        if slot and slot.status == "free" and client_profile:
            # Pre-fetch needed values BEFORE commit/flush to avoid MissingGreenlet
            trainer_name = slot.trainer_profile.user.full_name
            client_user_id = client_profile.user_id
            client_full_name = client_profile.full_name
            slot_start_time = slot.start_time
            slot_end_time = slot.end_time
            slot_zoom_url = slot.zoom_join_url
            slot_online_platform = slot.online_platform

            # Build full slot format string (Service + Format)
            selected_svc = data.get('selected_service', '')
            chosen_fmt = data.get('override_format', '')
            fmt_ru_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид", "offline": "оффлайн", "online": "онлайн", "hybrid": "гибрид"}

            slot_format = selected_svc
            if chosen_fmt:
                if slot_format:
                    slot_format += f" ({fmt_ru_map.get(chosen_fmt, chosen_fmt)})"
                else:
                    slot_format = fmt_ru_map.get(chosen_fmt, chosen_fmt)

            if not slot_format:
                slot_format = slot.format

            slot_price = data.get('override_price', slot.price)

            slot.status = "booked"
            slot.client_id = client_user_id
            slot.format = slot_format
            slot.price = slot_price

            new_booking = Booking(
                slot_id=slot_id,
                trainer_profile_id=slot.trainer_profile_id,
                client_id=client_id,
                start_time=slot_start_time,
                end_time=slot_end_time,
                status="confirmed",
                price=slot_price,
                paid=False
            )
            session.add(new_booking)
            await session.flush()

            booking_id = new_booking.id # Save ID for post-commit tasks

            # Setup reminders
            from src.services.reminders import ReminderService
            is_online = ("онлайн" in slot_format.lower() or "online" in slot_format.lower())
            await ReminderService.schedule_reminders(session, booking_id, client_user_id, pro_user_id, slot_start_time, slot_end_time, is_online=is_online)

            await session.commit()

            # Sync to Google Calendar
            try:
                from src.services.calendar import CalendarService
                await CalendarService.add_event_to_google(pro_user_id, booking_id)
            except Exception as e:
                logger.error(f"Failed to sync with Google Calendar for trainer {pro_user_id}: {e}")

            # Feedback to Professional
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="trainer_menu")]
            ])
            kb = add_admin_button(kb, is_admin=is_admin)
            text_success = f"✅ Клиент {client_full_name} успешно записан!"
            if callback.message.photo:
                await callback.message.edit_caption(caption=text_success, reply_markup=kb)
            else:
                await callback.message.edit_text(text_success, reply_markup=kb)

            # Notify client
            try:
                moscow_tz = gettz('Europe/Moscow')
                s_start = slot_start_time.replace(tzinfo=UTC) if slot_start_time.tzinfo is None else slot_start_time.astimezone(UTC)
                start_moscow = s_start.astimezone(moscow_tz)

                client_text = (
                    f"📅 **Вас записали на занятие!**\n\n"
                    f"👤 Мастер: {trainer_name}\n"
                    f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
                    f"🏷 Услуга: {slot_format}\n"
                )

                if ("онлайн" in slot_format.lower() or "online" in slot_format.lower()):
                    if slot_online_platform == "telegram":
                        client_text += "\n📱 **Формат:** Telegram Video\n**Инструкция:** Занятие будет проходить в этом чате по видеосвязи. Тренер свяжется с вами в назначенное время.\n"
                    elif slot_zoom_url:
                        client_text += f"\n🔗 **Ссылка на Zoom:** {slot_zoom_url}\n"

                client_text += "\nЗапись отображается в вашем профиле."
                await callback.bot.send_message(client_user_id, client_text, parse_mode="Markdown")
                logger.info(f"Notification sent to client {client_user_id}")
            except Exception as e:
                logger.error(f"Failed to notify client {client_user_id}: {e}")
        else:
            err_text = "❌ Ошибка при бронировании. Возможно, слот уже занят или клиент не найден."
            if callback.message.photo:
                await callback.message.edit_caption(caption=err_text)
            else:
                await callback.message.edit_text(err_text)

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "pro_cancel")
async def pro_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    cancel_text = "Запись отменена."
    if callback.message.photo:
        await callback.message.edit_caption(caption=cancel_text)
    else:
        await callback.message.edit_text(cancel_text)
    await callback.answer()
