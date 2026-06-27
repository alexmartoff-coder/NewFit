from aiogram import Router, types, F
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from src.models.models import User, ClientProfile, TrainerProfile, Booking
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button

router = Router()

@router.message(F.text == "Специалисты")
async def show_favorites(message: types.Message, is_admin: bool = False, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id

    async with SessionLocal() as session:
        # 1. Get client profile
        stmt_cp = select(ClientProfile).where(ClientProfile.user_id == user_id)
        client_profile = (await session.execute(stmt_cp)).scalar_one_or_none()

        if not client_profile:
            await message.answer("Профиль клиента не найден.")
            return

        # 2. Find unique trainers from bookings
        # We join Booking -> TrainerProfile -> User to get names
        stmt = (
            select(TrainerProfile, User)
            .join(Booking, Booking.trainer_profile_id == TrainerProfile.id)
            .join(User, TrainerProfile.user_id == User.id)
            .where(Booking.client_id == client_profile.id)
            .distinct(TrainerProfile.id)
            .options(selectinload(TrainerProfile.specializations))
        )

        res = await session.execute(stmt)
        specialists = res.all()

        if not specialists:
            await message.answer("Вы еще не записывались к специалистам. После первой записи они появятся здесь!")
            return

        await message.answer(f"Ваши специалисты ({len(specialists)}):")

        for profile, user_data in specialists:
            specs_str = ", ".join([s.name for s in profile.specializations]) or "не указаны"

            text = (
                f"👤 **{user_data.full_name}**\n"
                f"📍 {profile.city}"
                f"{f', {profile.district}' if profile.district else ''}\n"
                f"🎯 {specs_str}\n"
                f"⭐ Рейтинг: {profile.rating}"
            )

            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="📅 Записаться повторно", callback_data=f"book_{profile.user_id}")]
            ])
            kb = add_admin_button(kb, is_admin=is_admin)

            if profile.photo_url:
                await message.answer_photo(profile.photo_url, caption=text, reply_markup=kb, parse_mode="Markdown")
            else:
                await message.answer(text, reply_markup=kb, parse_mode="Markdown")
