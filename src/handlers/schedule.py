from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, delete, and_
from src.models.models import User, TimeSlot, TrainerSchedule
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from datetime import datetime, timedelta, time
import logging

router = Router()
logger = logging.getLogger(__name__)

class ScheduleState(StatesGroup):
    choosing_date = State()
    choosing_time = State()

@router.message(F.text == "📆 Расписание и запись")
@router.message(F.text == "/schedule")
async def show_schedule_menu(message: types.Message, is_admin: bool = False):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📅 Посмотреть слоты", callback_data="sche_view")],
            [types.InlineKeyboardButton(text="➕ Добавить слот", callback_data="sche_add")],
            [types.InlineKeyboardButton(text="🗑 Удалить слот", callback_data="sche_del")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer("Управление вашим расписанием:", reply_markup=kb)

@router.callback_query(F.data == "sche_view")
async def view_slots(callback: types.CallbackQuery, is_admin: bool = False):
    async with SessionLocal() as session:
        now = datetime.now()
        stmt = select(TimeSlot).where(
            TimeSlot.trainer_id == callback.from_user.id,
            TimeSlot.start_time >= now
        ).order_by(TimeSlot.start_time.asc())
        res = await session.execute(stmt)
        slots = res.scalars().all()

        kb_back = types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Назад", callback_data="sche_back")]]
        )
        kb_back = add_admin_button(kb_back, is_admin=is_admin)

        if not slots:
            await callback.message.edit_text("У вас пока нет запланированных слотов.", reply_markup=kb_back)
            return

        text = "Ваши ближайшие слоты:\n\n"
        for s in slots:
            status_icon = "🟢" if s.status == "free" else "🔴"
            text += f"{status_icon} {s.start_time.strftime('%d.%m %H:%M')} - {s.status}\n"

        await callback.message.edit_text(text, reply_markup=kb_back)
    await callback.answer()

@router.callback_query(F.data == "sche_add")
async def add_slot_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ScheduleState.choosing_date)
    await callback.message.answer("Введите дату для нового свободного слота (ДД.ММ.ГГГГ):")
    await callback.answer()

@router.message(ScheduleState.choosing_date)
async def add_slot_date(message: types.Message, state: FSMContext):
    try:
        date_obj = datetime.strptime(message.text, "%d.%m.%Y")
        if date_obj < datetime.now().replace(hour=0, minute=0, second=0, microsecond=0):
            await message.answer("Дата не может быть в прошлом. Попробуйте еще раз:")
            return
        await state.update_data(date=message.text)
        await state.set_state(ScheduleState.choosing_time)
        await message.answer("Введите время начала слота (ЧЧ:ММ):")
    except ValueError:
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ:")

@router.message(ScheduleState.choosing_time)
async def add_slot_time(message: types.Message, state: FSMContext):
    try:
        time_obj = datetime.strptime(message.text, "%H:%M")
        data = await state.get_data()
        date_obj = datetime.strptime(data['date'], "%d.%m.%Y")
        start_time = date_obj.replace(hour=time_obj.hour, minute=time_obj.minute)

        if start_time < datetime.now():
            await message.answer("Время не может быть в прошлом.")
            return

        async with SessionLocal() as session:
            new_slot = TimeSlot(
                trainer_id=message.from_user.id,
                start_time=start_time,
                end_time=start_time + timedelta(minutes=60),
                status="free"
            )
            session.add(new_slot)
            await session.commit()

        await message.answer(f"Слот на {start_time.strftime('%d.%m.%Y %H:%M')} успешно добавлен!")
        await state.clear()
    except ValueError:
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ:")

@router.callback_query(F.data == "sche_back")
async def sche_back(callback: types.CallbackQuery, is_admin: bool = False):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📅 Посмотреть слоты", callback_data="sche_view")],
            [types.InlineKeyboardButton(text="➕ Добавить слот", callback_data="sche_add")],
            [types.InlineKeyboardButton(text="🗑 Удалить слот", callback_data="sche_del")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    await callback.message.edit_text("Управление вашим расписанием:", reply_markup=kb)
    await callback.answer()
