from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.booking import BookingSession
from src.services.calendar import CalendarService
from src.models.models import TrainerProfile, User, ClientProfile, TimeSlot, Booking
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from sqlalchemy import select, update
from datetime import datetime, timedelta

router = Router()

@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    trainer_id = int(callback.data.split("_")[1])
    await state.update_data(trainer_id=trainer_id)

    # Send date selection (calendar view simulation for next 14 days)
    now = datetime.now().date()
    kb = []
    for i in range(14):
        d = now + timedelta(days=i)
        kb.append([types.InlineKeyboardButton(
            text=d.strftime("%d.%m (%a)"),
            callback_data=f"bdate_{d.isoformat()}"
        )])

    kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
    kb_markup = add_admin_button(kb_markup, is_admin=is_admin)
    await callback.message.edit_text("Выберите дату для записи:", reply_markup=kb_markup)
    await callback.answer()

@router.callback_query(F.data.startswith("bdate_"))
async def booking_date_selected(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    selected_date = datetime.fromisoformat(callback.data.split("_")[1]).date()
    data = await state.get_data()
    trainer_id = data['trainer_id']

    async with SessionLocal() as session:
        start_dt = datetime.combine(selected_date, datetime.min.time())
        end_dt = datetime.combine(selected_date, datetime.max.time())

        stmt = select(TimeSlot).where(
            TimeSlot.trainer_id == trainer_id,
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
        for s in slots:
            btn_text = f"{s.start_time.strftime('%H:%M')} — {s.format.value if hasattr(s.format, 'value') else s.format} ({s.price}₽)"
            kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"slot_{s.id}")])

        kb.append([types.InlineKeyboardButton(text="🔙 К выбору даты", callback_data=f"book_{trainer_id}")])
        kb_markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        kb_markup = add_admin_button(kb_markup, is_admin=is_admin)

        await callback.message.edit_text(f"Свободные слоты на {selected_date.strftime('%d.%m')}:", reply_markup=kb_markup)
    await callback.answer()

@router.callback_query(F.data.startswith("slot_"))
async def process_slot_selection(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
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
            f"Тренер ID: `{slot.trainer_id}`\n"
            f"Время: `{slot.start_time.strftime('%d.%m.%Y %H:%M')}`\n"
            f"Формат: `{slot.format.value if hasattr(slot.format, 'value') else slot.format}`\n"
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
    trainer_id = data['trainer_id']
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        # Re-check slot status inside transaction
        slot = await session.get(TimeSlot, slot_id)
        if slot and slot.status == "free":
            # 1. Update slot status
            slot.status = "booked"
            slot.client_id = user_id

            # 2. Create Booking record
            new_booking = Booking(
                slot_id=slot_id,
                trainer_id=trainer_id,
                client_id=user_id,
                status="confirmed"
            )
            session.add(new_booking)
            await session.commit()
            await callback.message.edit_text("Вы успешно записаны! Тренер увидит ваше бронирование в расписании.")
        else:
            await callback.message.edit_text("К сожалению, этот слот уже занят. Попробуйте выбрать другое время.")

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_booking", BookingSession.confirming_booking)
async def cancel_booking(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.answer()
