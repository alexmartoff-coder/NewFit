from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.booking import BookingSession
from src.services.calendar import CalendarService
from src.models.models import TrainerProfile, User, ClientProfile
from src.utils.db import SessionLocal
from sqlalchemy import select
from datetime import datetime, timedelta

router = Router()

@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: types.CallbackQuery, state: FSMContext):
    trainer_id = int(callback.data.split("_")[1])
    await state.update_data(trainer_id=trainer_id)
    await state.set_state(BookingSession.choosing_date)
    await callback.message.answer("Введите дату занятия в формате ДД.ММ.ГГГГ:")
    await callback.answer()

@router.message(BookingSession.choosing_date)
async def process_date(message: types.Message, state: FSMContext):
    try:
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        if date_obj < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            await message.answer("Дата не может быть в прошлом. Попробуйте еще раз:")
            return
        await state.update_data(date=message.text)
        await state.set_state(BookingSession.choosing_time)
        await message.answer("Введите время занятия в формате ЧЧ:ММ:")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуйте еще раз (ДД.ММ.ГГГГ):")

@router.message(BookingSession.choosing_time)
async def process_time(message: types.Message, state: FSMContext):
    try:
        time_obj = datetime.strptime(message.text, "%H:%M")
        data = await state.get_data()
        date_obj = datetime.strptime(data['date'], "%d.%m.%Y")
        start_time = date_obj.replace(hour=time_obj.hour, minute=time_obj.minute)

        if start_time < datetime.now():
            await message.answer("Время не может быть в прошлом. Попробуйте еще раз:")
            return

        await state.update_data(start_time=start_time.isoformat())
        await state.set_state(BookingSession.confirming_booking)

        await message.answer(
            f"Вы хотите записаться на {data['date']} в {message.text}.\n"
            "Подтвердить?",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="✅ Да", callback_data="confirm_booking")],
                    [types.InlineKeyboardButton(text="❌ Нет", callback_data="cancel_booking")]
                ]
            )
        )
    except ValueError:
        await message.answer("Неверный формат времени. Попробуйте еще раз (ЧЧ:ММ):")

@router.callback_query(F.data == "confirm_booking", BookingSession.confirming_booking)
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start_time = datetime.fromisoformat(data['start_time'])
    trainer_id = data['trainer_id']

    # Check availability
    if await CalendarService.is_available(trainer_id, start_time, start_time + timedelta(minutes=60)):
        async with SessionLocal() as session:
            stmt = select(ClientProfile.id).where(ClientProfile.user_id == callback.from_user.id)
            res = await session.execute(stmt)
            client_id = res.scalar_one()

            await CalendarService.create_booking(trainer_id, client_id, start_time)
            await callback.message.edit_text("Запись успешно создана! Тренер получит уведомление.")
    else:
        await callback.message.edit_text("К сожалению, это время уже занято. Выберите другое.")

    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_booking", BookingSession.confirming_booking)
async def cancel_booking(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.answer()
