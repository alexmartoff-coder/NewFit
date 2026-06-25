from aiogram import Router, types, F, exceptions
from aiogram.fsm.context import FSMContext
from src.states.booking import BookingSession
from src.services.calendar import CalendarService
from src.services.payments import PaymentService
from src.models.models import TrainerProfile, User, ClientProfile, TimeSlot, Booking, UserRole
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from sqlalchemy import select, update
from datetime import datetime, timedelta
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    trainer_user_id = int(callback.data.split("_")[1])

    # Resolve professional profile
    async with SessionLocal() as session:
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == trainer_user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль профессионала не найден!")
            return

        trainer_profile_id = profile.id
        await state.update_data(trainer_profile_id=trainer_profile_id, trainer_user_id=trainer_user_id)

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
        for d in available_dates:
            kb.append([types.InlineKeyboardButton(
                text=d.strftime("%d.%m (%a)"),
                callback_data=f"bdate_{d.isoformat()}"
            )])
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
        fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид"}
        from dateutil.tz import gettz, UTC
        moscow_tz = gettz('Europe/Moscow')

        for s in slots:
            # Ensure MSK conversion for button labels
            s_start = s.start_time.replace(tzinfo=UTC) if s.start_time.tzinfo is None else s.start_time.astimezone(UTC)
            s_end = s.end_time.replace(tzinfo=UTC) if s.end_time.tzinfo is None else s.end_time.astimezone(UTC)

            start_str = s_start.astimezone(moscow_tz).strftime('%H:%M')
            end_str = s_end.astimezone(moscow_tz).strftime('%H:%M')

            fmt_val = s.format.value if hasattr(s.format, 'value') else str(s.format)
            fmt_ru = fmt_map.get(fmt_val, fmt_val.lower())

            btn_text = f"{start_str} - {end_str} — {int(s.price)}₽ ({fmt_ru})"
            kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"slot_{s.id}")])

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
    slot_id = int(callback.data.split("_")[1])

    async with SessionLocal() as session:
        # Load slot and trainer role
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user))
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        if not slot or slot.status != "free":
            text = "Этот слот уже занят или недоступен. Выберите другой."
            if callback.message.photo:
                await callback.message.edit_caption(caption=text)
            else:
                await callback.message.edit_text(text)
            return

        await state.update_data(slot_id=slot_id, start_time=slot.start_time.isoformat())
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

        term_format = "Услуга" if (is_beauty or is_specific_sport) else "Формат"

        # Try to use the selected service from state if it's broad 'hybrid'
        display_format = slot.format
        if slot.format.lower() == "hybrid" and specs:
            display_format = ", ".join(specs)
            # Update slot format in state to carry over to booking
            await state.update_data(override_format=display_format)

        selected_date = s_start.date().isoformat()
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Да, записаться", callback_data="confirm_booking")],
                [types.InlineKeyboardButton(text="🔙 К выбору времени", callback_data=f"bdate_{selected_date}")],
                [types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="client_menu")]
            ]
        )
        kb = add_admin_button(kb, is_admin=is_admin)

        text = (
            f"📍 **Подтверждение записи**\n\n"
            f"Время: `{start_moscow.strftime('%d.%m.%Y %H:%M')}` (МСК)\n"
            f"{term_format}: `{display_format}`\n"
            f"Цена: `{slot.price}₽`\n\n"
            f"Нажмите подтвердить для завершения записи."
        )
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

from sqlalchemy.orm import selectinload

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
            selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user)
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        if slot and slot.status == "free":
            # Pre-fetch all necessary attributes before commit to avoid MissingGreenlet
            client_name = client_profile.full_name
            trainer_user_id = slot.trainer_profile.user_id
            slot_start = slot.start_time
            slot_end = slot.end_time
            slot_price = slot.price

            # Override format if specialized service was selected
            slot_format = data.get('override_format', slot.format)

            # Determine role-specific terminology
            from src.models.models import UserRole
            is_beauty = slot.trainer_profile.user.role == UserRole.BEAUTY
            is_specific_sport = any(s in ["Большой теннис", "Падл"] for s in slot_format.split(", "))

            term_lesson = "на услугу" if (is_beauty or is_specific_sport) else "на тренировку"
            term_format = "Услуга" if (is_beauty or is_specific_sport) else "Формат"

            slot.status = "booked"
            slot.client_id = user_id
            slot.format = slot_format # Store the specific service name

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
            await ReminderService.schedule_reminders(session, new_booking.id, user_id, slot_start)

            await session.commit()

            text = f"✅ **Запись успешно подтверждена!**\n\nВы успешно записаны {term_lesson}.\n📅 Мы пришлем вам напоминание за 24 и 2 часа до начала."

            # Show main menu keyboard to client
            from src.keyboards.common import get_client_main_kb
            kb = get_client_main_kb()

            if callback.message.photo:
                await callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
            else:
                try:
                    await callback.message.edit_text(text, reply_markup=None, parse_mode="Markdown")
                except exceptions.TelegramBadRequest:
                    pass
                await callback.message.answer("Воспользуйтесь меню ниже для навигации:", reply_markup=kb)

            # Notify professional
            try:
                from dateutil.tz import gettz, UTC
                moscow_tz = gettz('Europe/Moscow')

                # Convert time to Moscow for notification
                s_start = slot_start.replace(tzinfo=UTC) if slot_start.tzinfo is None else slot_start.astimezone(UTC)
                start_moscow = s_start.astimezone(moscow_tz)

                trainer_text = (
                    f"🆕 **Новая запись!**\n\n"
                    f"👤 Клиент: {client_name}\n"
                    f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
                    f"🏷 {term_format}: {slot_format}\n"
                    f"💰 Цена: {slot_price}₽"
                )
                await callback.bot.send_message(trainer_user_id, trainer_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to notify professional {slot.trainer_profile.user_id}: {e}")
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
