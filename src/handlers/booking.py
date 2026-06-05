from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.booking import BookingSession
from src.services.calendar import CalendarService
from src.models.models import TrainerProfile, User, ClientProfile, TimeSlot, Booking
from src.utils.db import SessionLocal
from sqlalchemy import select, update
from datetime import datetime, timedelta

router = Router()

@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: types.CallbackQuery, state: FSMContext):
    trainer_id = int(callback.data.split("_")[1])
    await state.update_data(trainer_id=trainer_id)

    async with SessionLocal() as session:
        # Fetch available slots for next 7 days
        now = datetime.now()
        end = now + timedelta(days=7)
        stmt = select(TimeSlot).where(
            TimeSlot.trainer_id == trainer_id,
            TimeSlot.status == "free",
            TimeSlot.start_time >= now,
            TimeSlot.start_time <= end
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        if not slots:
            await callback.message.answer("У этого тренера нет свободных слотов на ближайшую неделю.")
            await callback.answer()
            return

        kb = []
        for s in slots:
            btn_text = s.start_time.strftime("%d.%m %H:%M")
            kb.append([types.InlineKeyboardButton(text=btn_text, callback_data=f"slot_{s.id}")])

        await callback.message.edit_text(
            "Выберите удобное время для записи:",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb)
        )
    await callback.answer()

@router.callback_query(F.data.startswith("slot_"))
async def process_slot_selection(callback: types.CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_")[1])

    async with SessionLocal() as session:
        slot = await session.get(TimeSlot, slot_id)
        if not slot or slot.status != "free":
            await callback.message.edit_text("Этот слот уже занят или недоступен. Выберите другой.")
            return

        await state.update_data(slot_id=slot_id, start_time=slot.start_time.isoformat())
        await state.set_state(BookingSession.confirming_booking)

        await callback.message.edit_text(
            f"Вы выбрали время: {slot.start_time.strftime('%d.%m.%Y %H:%M')}.\n"
            "Подтвердить запись?",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="✅ Да, записаться", callback_data="confirm_booking")],
                    [types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_booking")]
                ]
            )
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
