import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func, update
from src.models.models import Review, Booking, TrainerProfile, User
from src.utils.db import SessionLocal
from src.states.review import ReviewStates

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data.startswith("leave_review_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    booking_id = int(callback.data.split("_")[2])

    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        if not booking:
            await callback.answer("Запись не найдена.")
            return

        # Check if already reviewed
        existing_review = await session.execute(
            select(Review).where(Review.booking_id == booking_id)
        )
        if existing_review.scalar_one_or_none():
            await callback.answer("Вы уже оставили отзыв на эту запись.", show_alert=True)
            return

    await state.update_data(booking_id=booking_id, trainer_id=booking.trainer_profile_id)
    await state.set_state(ReviewStates.waiting_for_rating)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⭐", callback_data="rate_1"),
         types.InlineKeyboardButton(text="⭐⭐", callback_data="rate_2"),
         types.InlineKeyboardButton(text="⭐⭐⭐", callback_data="rate_3"),
         types.InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data="rate_4"),
         types.InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data="rate_5")]
    ])

    await callback.message.answer("Пожалуйста, оцените работу мастера от 1 до 5:", reply_markup=kb)
    await callback.answer()

@router.callback_query(ReviewStates.waiting_for_rating, F.data.startswith("rate_"))
async def process_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)

    await state.set_state(ReviewStates.waiting_for_comment)

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Пропустить", callback_data="skip_comment")]
    ])

    await callback.message.edit_text(f"Вы выбрали {rating} ⭐. Добавьте текстовый комментарий (необязательно):", reply_markup=kb)
    await callback.answer()

@router.callback_query(ReviewStates.waiting_for_comment, F.data == "skip_comment")
async def skip_comment(callback: types.CallbackQuery, state: FSMContext):
    await save_review(callback.message, state, comment=None)
    await callback.answer()

@router.message(ReviewStates.waiting_for_comment)
async def process_comment(message: types.Message, state: FSMContext):
    await save_review(message, state, comment=message.text)

async def save_review(message: types.Message, state: FSMContext, comment: str = None):
    data = await state.get_data()
    booking_id = data['booking_id']
    trainer_profile_id = data['trainer_id']
    rating = data['rating']

    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        if not booking:
            await message.answer("Ошибка: запись не найдена.")
            await state.clear()
            return

        client_id = booking.client_id

        new_review = Review(
            trainer_id=trainer_profile_id,
            client_id=client_id,
            booking_id=booking_id,
            rating=rating,
            comment=comment
        )
        session.add(new_review)
        await session.flush()

        # Recalculate average rating for trainer
        avg_rating_stmt = select(func.avg(Review.rating)).where(Review.trainer_id == trainer_profile_id)
        avg_res = await session.execute(avg_rating_stmt)
        avg_val = avg_res.scalar() or 5.0

        # Update trainer profile
        await session.execute(
            update(TrainerProfile)
            .where(TrainerProfile.id == trainer_profile_id)
            .values(rating=float(avg_val))
        )

        await session.commit()

    await message.answer("Спасибо за ваш отзыв! ❤️ Он поможет другим пользователям выбрать лучшего мастера.")
    await state.clear()
