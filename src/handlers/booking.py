from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.booking import BookingSession
from src.services.calendar import CalendarService
from src.services.payments import PaymentService
from src.models.models import TrainerProfile, User, ClientProfile, TimeSlot, Booking
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from sqlalchemy import select, update
from datetime import datetime, timedelta

router = Router()

@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    trainer_user_id = int(callback.data.split("_")[1])

    # Resolve trainer profile
    async with SessionLocal() as session:
        stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == trainer_user_id)
        profile = (await session.execute(stmt_p)).scalar_one_or_none()
        if not profile:
            await callback.answer("Профиль тренера не найден!")
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
            await callback.message.answer("К сожалению, у этого тренера нет свободных слотов на ближайшее время.")
            await callback.answer()
            return

        kb = []
        for d in available_dates:
            kb.append([types.InlineKeyboardButton(
                text=d.strftime("%d.%m (%a)"),
                callback_data=f"bdate_{d.isoformat()}"
            )])

    kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    kb_markup = add_admin_button(kb_markup, is_admin=is_admin)
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
        for s in slots:
            start_str = s.start_time.strftime('%H:%M')
            end_str = s.end_time.strftime('%H:%M')
            fmt_val = s.format.value if hasattr(s.format, 'value') else str(s.format)
            fmt_ru = fmt_map.get(fmt_val, fmt_val.lower())

            btn_text = f"{start_str} - {end_str} — {int(s.price)}₽ ({fmt_ru})"
            kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"slot_{s.id}")])

        kb.append([types.InlineKeyboardButton(text="🔙 К выбору даты", callback_data=f"book_{trainer_user_id}")])
        kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        kb_markup = add_admin_button(kb_markup, is_admin=is_admin)

        await callback.message.edit_text(f"Свободные слоты на {selected_date.strftime('%d.%m')}:", reply_markup=kb_markup)
    await callback.answer()

@router.callback_query(F.data.startswith("slot_"))
async def process_slot_selection(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    slot_id = int(callback.data.split("_")[1])

    async with SessionLocal() as session:
        slot = await session.get(TimeSlot, slot_id)
        if not slot or slot.status != "free":
            await callback.message.edit_text("Этот слот уже занят или недоступен. Выберите другой.")
            return

        await state.update_data(slot_id=slot_id, start_time=slot.start_time.isoformat())
        await state.set_state(BookingSession.confirming_booking)

        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Да, записаться", callback_data="confirm_booking")],
                [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking")]
            ]
        )
        kb = add_admin_button(kb, is_admin=is_admin)

        await callback.message.edit_text(
            f"📍 **Подтверждение записи**\n\n"
            f"Время: `{slot.start_time.strftime('%d.%m.%Y %H:%M')}`\n"
            f"Формат: `{slot.format}`\n"
            f"Цена: `{slot.price}₽`\n\n"
            f"💳 После подтверждения вам придет ссылка на оплату.",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data == "confirm_booking", BookingSession.confirming_booking)
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    data = await state.get_data()
    slot_id = data['slot_id']
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        slot = await session.get(TimeSlot, slot_id)
        if not slot or slot.status != "free":
            await callback.message.edit_text("К сожалению, этот слот уже занят.")
            return

        # Use mock payment link
        payment_link = await PaymentService.create_payment_link(slot.price, f"Запись на {slot.start_time}", user_id)

        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 Оплатить", url=payment_link)],
            [types.InlineKeyboardButton(text="✅ Я оплатил (симуляция)", callback_data=f"pay_success_{slot_id}")]
        ])

        await callback.message.edit_text(
            f"Для завершения записи на {slot.start_time.strftime('%d.%m %H:%M')} необходимо оплатить `{slot.price}₽`.\n\n"
            "После оплаты ваша запись будет подтверждена автоматически.",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("pay_success_"))
async def process_mock_payment(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    slot_id = int(callback.data.split("_")[2])
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        slot = await session.get(TimeSlot, slot_id)
        if slot and slot.status == "free":
            slot.status = "booked"
            slot.client_id = user_id

            new_booking = Booking(
                slot_id=slot_id,
                trainer_id=slot.trainer_profile.user_id,
                client_id=user_id,
                status="confirmed",
                price=slot.price,
                paid=True
            )
            session.add(new_booking)
            await session.flush()

            # Setup reminders
            from src.services.reminders import ReminderService
            await ReminderService.schedule_reminders(session, new_booking.id, user_id, slot.start_time)

            await session.commit()
            await callback.message.edit_text("💳 Оплата прошла успешно!\n\nВы записаны на тренировку. Мы пришлем вам напоминание за 24 и 2 часа до начала.")
        else:
            await callback.message.edit_text("Срок действия оплаты истек или слот уже занят.")

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_booking", BookingSession.confirming_booking)
async def cancel_booking(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.answer()
