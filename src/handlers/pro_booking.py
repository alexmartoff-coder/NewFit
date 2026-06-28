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
async def pro_start_booking(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    client_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

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
        kb.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="clients_list")]) # To be implemented or handled

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
        slot = await session.get(TimeSlot, slot_id)
        if not slot or slot.status != "free":
            await callback.answer("Слот уже занят")
            return

        data = await state.get_data()
        await state.update_data(slot_id=slot_id)

        moscow_tz = gettz('Europe/Moscow')
        s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
        start_moscow = s_start.astimezone(moscow_tz)

        text = (
            f"❓ **Подтвердите запись клиента**\n\n"
            f"👤 Клиент: {data['client_name']}\n"
            f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
            f"🏷 Формат/Услуга: {slot.format}\n"
            f"💰 Цена: {slot.price}₽"
        )

        kb = [
            [types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="pro_confirm_booking")],
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="pro_cancel")]
        ]

        await state.set_state(ProBookingSession.confirming)
        await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "pro_confirm_booking", ProBookingSession.confirming)
async def pro_confirm_booking(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    slot_id = data['slot_id']
    client_id = data['client_id']

    async with SessionLocal() as session:
        stmt = select(TimeSlot).where(TimeSlot.id == slot_id).options(
            selectinload(TimeSlot.trainer_profile).selectinload(TrainerProfile.user)
        )
        res = await session.execute(stmt)
        slot = res.scalar_one_or_none()

        client_profile = await session.get(ClientProfile, client_id, options=[selectinload(ClientProfile.user)])

        if slot and slot.status == "free" and client_profile:
            slot.status = "booked"
            slot.client_id = client_profile.user_id

            new_booking = Booking(
                slot_id=slot_id,
                trainer_profile_id=slot.trainer_profile_id,
                client_id=client_id,
                start_time=slot.start_time,
                end_time=slot.end_time,
                status="confirmed",
                price=slot.price,
                paid=False
            )
            session.add(new_booking)
            await session.flush()

            # Setup reminders
            from src.services.reminders import ReminderService
            await ReminderService.schedule_reminders(session, new_booking.id, client_profile.user_id, slot.start_time)

            await session.commit()

            await callback.message.edit_text(f"✅ Клиент {client_profile.full_name} успешно записан!")

            # Notify client
            try:
                moscow_tz = gettz('Europe/Moscow')
                s_start = slot.start_time.replace(tzinfo=UTC) if slot.start_time.tzinfo is None else slot.start_time.astimezone(UTC)
                start_moscow = s_start.astimezone(moscow_tz)

                trainer_name = slot.trainer_profile.user.full_name
                client_text = (
                    f"📅 **Вас записали на занятие!**\n\n"
                    f"👤 Мастер: {trainer_name}\n"
                    f"⏰ Время: {start_moscow.strftime('%d.%m %H:%M')}\n"
                    f"🏷 Услуга: {slot.format}\n\n"
                    "Запись отображается в вашем профиле."
                )
                await callback.bot.send_message(client_profile.user_id, client_text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to notify client {client_profile.user_id}: {e}")
        else:
            await callback.message.edit_text("❌ Ошибка при бронировании. Возможно, слот уже занят.")

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "pro_cancel")
async def pro_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.answer()
