import logging
from datetime import datetime, timedelta, timezone
from dateutil.tz import gettz, UTC

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from src.models.models import User, TrainerProfile, ClientProfile, UserRole, Booking, TimeSlot
from src.utils.db import SessionLocal
from src.states.pro_booking import ProBookingSession
from src.keyboards.inline import add_admin_button

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("pro_book_client_"))
async def pro_start_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    client_id = int(callback.data.split("_")[-1])
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        # Get professional profile
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль не найден")
            return

        # Get client profile to show name
        client = await session.get(ClientProfile, client_id)
        if not client:
            await callback.answer("Клиент не найден")
            return

        await state.update_data(client_id=client_id, trainer_profile_id=profile.id, client_name=client.full_name)

        # Find available dates
        now = datetime.now()
        end_view = now + timedelta(days=30)
        stmt = select(TimeSlot.start_time).where(
            TimeSlot.trainer_profile_id == profile.id,
            TimeSlot.status == "free",
            TimeSlot.start_time >= now,
            TimeSlot.start_time <= end_view
        )
        res = await session.execute(stmt)
        available_dates = sorted(list(set(dt.date() for dt in res.scalars().all())))

        if not available_dates:
            await callback.message.answer("У вас нет свободных слотов в расписании. Сначала добавьте слоты.")
            await callback.answer()
            return

        kb = []
        for d in available_dates:
            kb.append([types.InlineKeyboardButton(
                text=d.strftime("%d.%m (%a)"),
                callback_data=f"pro_bdate_{d.isoformat()}"
            )])
        kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="clients_list")]) # To be handled by show_clients

    await state.set_state(ProBookingSession.choosing_date)
    await callback.message.edit_text(f"Выберите дату для записи клиента {client.full_name}:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("pro_bdate_"), ProBookingSession.choosing_date)
async def pro_date_selected(callback: types.CallbackQuery, state: FSMContext):
    selected_date = datetime.fromisoformat(callback.data.split("_")[-1]).date()
    data = await state.get_data()
    trainer_profile_id = data['trainer_profile_id']

    async with SessionLocal() as session:
        start_dt = datetime.combine(selected_date, datetime.min.time())
        end_dt = datetime.combine(selected_date, datetime.max.time())

        stmt = select(TimeSlot).where(
            TimeSlot.trainer_profile_id == trainer_profile_id,
            TimeSlot.status == "free",
            TimeSlot.start_time >= start_dt,
            TimeSlot.start_time <= end_dt
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        if not slots:
            await callback.answer("На этот день нет свободных слотов")
            return

        kb = []
        moscow_tz = gettz('Europe/Moscow')
        for s in slots:
            s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
            start_str = s_start.astimezone(moscow_tz).strftime('%H:%M')
            kb.append([types.InlineKeyboardButton(text=f"{start_str} — {s.format}", callback_data=f"pro_slot_{s.id}")])

        kb.append([types.InlineKeyboardButton(text="🔙 К выбору даты", callback_data=f"pro_book_client_{data['client_id']}")])

        await state.set_state(ProBookingSession.choosing_slot)
        await callback.message.edit_text(f"Выберите время на {selected_date.strftime('%d.%m')}:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@router.callback_query(F.data.startswith("pro_slot_"), ProBookingSession.choosing_slot)
async def pro_slot_selected(callback: types.CallbackQuery, state: FSMContext):
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
            await callback.answer("Слот уже занят")
            return

        await state.update_data(slot_id=slot_id)

        # Step 1: Choose Service/Direction
        specs = slot.trainer_profile.specializations
        if specs:
            await state.set_state(ProBookingSession.choosing_service)
            kb = []
            for spec in specs:
                kb.append([types.InlineKeyboardButton(text=spec.name, callback_data=f"pro_svc_{spec.name}")])
            kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"pro_bdate_{slot.start_time.date().isoformat()}")])

            role = slot.trainer_profile.user.role
            term = "услугу" if role in [UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL] else "направление"
            await callback.message.edit_text(f"Выберите {term} для этой записи:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
            return

        await proceed_to_format_or_confirm(callback, state, slot)
    await callback.answer()

@router.callback_query(F.data.startswith("pro_svc_"), ProBookingSession.choosing_service)
async def pro_service_selected(callback: types.CallbackQuery, state: FSMContext):
    service_name = callback.data.replace("pro_svc_", "")
    await state.update_data(selected_service=service_name)

    data = await state.get_data()
    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == data['slot_id']).options(
            selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user)
        )
        slot = (await session.execute(stmt)).scalar_one_or_none()
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
        await callback.message.edit_text("Выберите формат для этой записи:", reply_markup=kb)
        return

    await show_pro_booking_confirmation(callback, state, slot)

@router.callback_query(F.data.startswith("pro_fmt_"), ProBookingSession.choosing_format)
async def pro_format_selected(callback: types.CallbackQuery, state: FSMContext):
    fmt = callback.data.split("_")[2]
    await state.update_data(override_format=fmt)
    data = await state.get_data()
    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == data['slot_id']).options(
            selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user)
        )
        slot = (await session.execute(stmt)).scalar_one_or_none()
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

    text = (
        f"❓ **Подтвердите запись клиента**\n\n"
        f"👤 Клиент: {data['client_name']}\n"
        f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
        f"🏷 {term_format}: {display_format}\n"
        f"💰 Цена: {slot.price}₽"
    )

    kb = [
        [types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="pro_confirm_booking")],
        [types.InlineKeyboardButton(text="❌ Отмена", callback_data="pro_cancel")]
    ]

    await state.set_state(ProBookingSession.confirming)
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data == "pro_confirm_booking", ProBookingSession.confirming)
async def pro_confirm_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    data = await state.get_data()
    slot_id = data['slot_id']
    client_id = data['client_id']
    pro_user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user)
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        client_profile = await session.get(ClientProfile, client_id, options=[selectinload(ClientProfile.user)])

        if slot and slot.status == "free" and client_profile:
            # Pre-fetch needed values
            trainer_name = slot.trainer_profile.user.full_name
            client_user_id = client_profile.user_id
            client_full_name = client_profile.full_name
            slot_start_time = slot.start_time
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

            slot_price = slot.price

            slot.status = "booked"
            slot.client_id = client_user_id
            slot.format = slot_format

            new_booking = Booking(
                slot_id=slot_id,
                trainer_profile_id=slot.trainer_profile_id,
                client_id=client_id,
                start_time=slot.start_time,
                end_time=slot.end_time,
                status="confirmed",
                price=slot_price,
                paid=False
            )
            session.add(new_booking)
            await session.flush()

            # Setup reminders
            from src.services.reminders import ReminderService
            is_online = ("онлайн" in slot_format.lower() or "online" in slot_format.lower())
            await ReminderService.schedule_reminders(session, new_booking.id, client_user_id, pro_user_id, slot_start_time, is_online=is_online)

            await session.commit()

            # Sync to Google Calendar
            try:
                from src.services.calendar import CalendarService
                await CalendarService.add_event_to_google(pro_user_id, new_booking.id)
            except Exception as e:
                logger.error(f"Failed to sync with Google Calendar for trainer {pro_user_id}: {e}")

            # Feedback to Professional
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="trainer_menu")]
            ])
            kb = add_admin_button(kb, is_admin=is_admin)
            await callback.message.edit_text(f"✅ Клиент {client_full_name} успешно записан!", reply_markup=kb)

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
            await callback.message.edit_text("❌ Ошибка при бронировании. Возможно, слот уже занят или клиент не найден.")

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "pro_cancel")
async def pro_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.answer()
