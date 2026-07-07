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
from datetime import datetime, timedelta
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

        now = datetime.now()
        end_view = now + timedelta(days=14)
        stmt = select(TimeSlot.start_time).where(
            TimeSlot.trainer_profile_id == trainer_profile_id,
            TimeSlot.status == "free",
            TimeSlot.start_time >= now,
            TimeSlot.start_time <= end_view
        )
        res = await session.execute(stmt)
        available_dates = sorted(list(set(dt.date() for dt in res.scalars().all())))

        if not available_dates:
            await callback.message.answer("К сожалению, у этого профессионала нет свободных слотов на ближайшее время.")
            await callback.answer()
            return

        kb = []
        row = []
        for d in available_dates:
            row.append(types.InlineKeyboardButton(
                text=d.strftime("%d.%m (%a)"),
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

    if callback.message.photo:
        await callback.message.edit_caption(caption="Выберите дату для записи:", reply_markup=kb_markup)
    else:
        await callback.message.edit_text("Выберите дату для записи:", reply_markup=kb_markup)
    await callback.answer()

@router.callback_query(F.data.startswith("bdate_"))
async def booking_date_selected(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    selected_date = datetime.fromisoformat(callback.data.split("_")[1]).date()
    data = await state.get_data()
    trainer_profile_id = data['trainer_profile_id']
    trainer_user_id = data['trainer_user_id']

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
            await callback.message.answer("На этот день нет свободных слотов. Выберите другую дату.")
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

            btn_text = f"{start_str}-{end_str}"
            row.append(types.InlineKeyboardButton(text=btn_text, callback_data=f"slot_{s.id}"))
            if len(row) == 2:
                kb.append(row)
                row = []

        if row:
            kb.append(row)

        kb.append([types.InlineKeyboardButton(text="🔙 К выбору даты", callback_data=f"book_{trainer_user_id}")])
        kb.append([types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="client_menu")])
        kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        kb_markup = add_admin_button(kb_markup, is_admin=is_admin)

        text = f"Свободные слоты на {selected_date.strftime('%d.%m')}:"
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb_markup)
        else:
            await callback.message.edit_text(text, reply_markup=kb_markup)
    await callback.answer()

@router.callback_query(F.data.startswith("slot_"))
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

        if not slot or slot.status != "free":
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

        details = (
            f"⏰ *{start_moscow.strftime('%d.%m %H:%M')}—{end_moscow.strftime('%H:%M')}*\n"
            f"📍 {fmt_text}\n"
            f"💰 Цена: {int(slot.price)}₽\n"
        )
        if slot.trainer_profile and slot.trainer_profile.user:
            details += f"👤 Мастер: {escape_md(slot.trainer_profile.user.full_name)}\n"

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Записаться на это время", callback_data=f"slot_confirm_{slot.id}")],
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

        if not slot or slot.status != "free":
            text = "Этот слот уже занят или недоступен."
            await callback.message.answer(text)
            return

        await state.update_data(slot_id=slot_id, start_time=slot.start_time.isoformat())

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

            text = f"{price_text}\n\nВыберите {term} для записи:"
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
    # Check if we need to ask for format (offline/online)
    # We ask if the specialist's slot format is 'hybrid'
    if slot.format.lower() == "hybrid" or slot.format.lower() == "гибрид":
        await state.set_state(BookingSession.choosing_format)
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🏢 Оффлайн", callback_data="c_fmt_offline")],
            [types.InlineKeyboardButton(text="💻 Онлайн (дистанционно)", callback_data="c_fmt_online")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data=f"slot_{slot.id}")]
        ])

        data = await state.get_data()
        current_price = data.get('override_price', slot.price)
        text = f"Цена: `{int(current_price)}₽`\n\nЭтот специалист проводит занятия и оффлайн, и онлайн. Выберите удобный вам формат:"
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        return

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
    start_moscow = s_start.astimezone(moscow_tz)

    # Dynamic terminology based on specialist role
    data = await state.get_data()
    specs = data.get('specializations', [])

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
            [types.InlineKeyboardButton(text="✅ Да, записаться", callback_data="confirm_booking")],
            [types.InlineKeyboardButton(text="🔙 К выбору времени", callback_data=f"bdate_{selected_date}")],
            [types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="client_menu")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)

    display_price = data.get('override_price', slot.price)

    text = (
        f"📍 *Подтверждение записи*\n\n"
        f"Время: `{start_moscow.strftime('%d.%m.%Y %H:%M')}` (МСК)\n"
        f"{term_format}: `{escape_md(display_format)}`\n"
        f"Цена: `{int(display_price)}₽`\n\n"
        f"Нажмите подтвердить для завершения записи."
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data == "confirm_booking", BookingSession.confirming_booking)
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    data = await state.get_data()
    slot_id = data['slot_id']
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        # Safety check: ensure client user exists in 'users' table
        client_user = await session.get(User, user_id)
        if not client_user:
            # Fallback for impersonation or accidental deletion: recreate the user
            client_user = User(
                id=user_id,
                username=callback.from_user.username,
                full_name=callback.from_user.full_name or f"User {user_id}",
                role=UserRole.CLIENT
            )
            session.add(client_user)
            await session.flush()

        # 1. Автосоздание профиля клиента
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
            await session.flush() # Получаем ID

        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.trainer_profile).options(
                selectinload(TrainerProfile.user)
            )
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        if slot and slot.status == "free":
            # Pre-fetch all necessary attributes before commit to avoid MissingGreenlet
            client_name = client_profile.full_name
            trainer_user_id = slot.trainer_profile.user_id
            slot_start = slot.start_time
            slot_end = slot.end_time
            slot_price = data.get('override_price', slot.price)
            slot_online_platform = slot.online_platform
            slot_zoom_join_url = slot.zoom_join_url

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

            # Determine role-specific terminology
            is_beauty = slot.trainer_profile.user.role == UserRole.BEAUTY
            is_specific_sport = any(s in ["Большой теннис", "Падл"] for s in slot_format.split(", "))

            term_lesson = "на услугу" if (is_beauty or is_specific_sport) else "на тренировку"
            term_format = "Услуга" if (is_beauty or is_specific_sport) else "Формат"

            slot.status = "booked"
            slot.client_id = user_id
            slot.format = slot_format # Store the specific service name
            slot.price = slot_price   # Store the final price for this booking

            new_booking = Booking(
                slot_id=slot_id,
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

            # Setup reminders
            from src.services.reminders import ReminderService
            is_online = ("онлайн" in slot_format.lower() or "online" in slot_format.lower())
            await ReminderService.schedule_reminders(session, new_booking.id, user_id, trainer_user_id, slot_start, slot_end, is_online=is_online)

            await session.commit()

            # Sync to Google Calendar
            try:
                from src.services.calendar import CalendarService
                await CalendarService.add_event_to_google(trainer_user_id, new_booking.id)
            except Exception as e:
                logger.error(f"Failed to sync with Google Calendar for trainer {trainer_user_id}: {e}")

            text = f"✅ *Запись успешно подтверждена!*\n\nВы успешно записаны {term_lesson}.\n📅 Мы пришлем вам напоминание за 24 и 2 часа до начала."

            if ("онлайн" in slot_format.lower() or "online" in slot_format.lower()):
                if slot_online_platform == "telegram":
                    text += f"\n\n📱 *Формат:* Telegram Video\n*Инструкция:* Занятие будет проходить в этом чате по видеосвязи. Тренер свяжется с вами в назначенное время."
                elif slot_zoom_join_url:
                    text += f"\n\n🔗 *Ссылка на Zoom:* {escape_md(slot_zoom_join_url)}"
                else:
                    text += f"\n\n📱 *Формат:* Онлайн\n*Услуга:* {escape_md(slot_format)}"

            # Show main menu keyboard to client
            from src.keyboards.common import get_client_main_kb
            # After a successful booking, the user definitely has at least one specialist now
            kb = get_client_main_kb(has_specialists=True)

            # Cleanup confirmation screen
            try:
                await callback.message.delete()
            except Exception:
                try:
                    await callback.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass

            # Send final confirmation message
            # Explicitly use bot.send_message for reliability after potential delete
            await callback.bot.send_message(
                chat_id=callback.message.chat.id,
                text=text,
                reply_markup=kb,
                parse_mode="Markdown"
            )

            # Notify professional
            try:
                from dateutil.tz import gettz, UTC
                moscow_tz = gettz('Europe/Moscow')

                # Convert time to Moscow for notification
                s_start = slot_start.replace(tzinfo=UTC) if slot_start.tzinfo is None else slot_start.astimezone(UTC)
                start_moscow = s_start.astimezone(moscow_tz)

                trainer_text = (
                    f"🆕 *Новая запись!*\n\n"
                    f"👤 Клиент: {escape_md(client_name)}\n"
                    f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
                    f"🏷 {term_format}: {escape_md(slot_format)}\n"
                    f"💰 Цена: {slot_price}₽"
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
