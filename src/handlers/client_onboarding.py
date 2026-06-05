from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import User, ClientProfile, UserRole
from src.utils.db import SessionLocal
from src.keyboards.common import get_client_main_kb

router = Router()

@router.message(F.text == "🏋️‍♀️ Я клиент")
async def client_start(message: types.Message, is_admin: bool = False):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(
                id=message.from_user.id,
                username=message.from_user.username,
                full_name=message.from_user.full_name,
                role=UserRole.CLIENT
            )
            session.add(user)
        else:
            user.role = UserRole.CLIENT

        stmt = select(ClientProfile).where(ClientProfile.user_id == user.id)
        res = await session.execute(stmt)
        client_profile = res.scalar_one_or_none()

        if not client_profile:
            client_profile = ClientProfile(user_id=user.id)
            session.add(client_profile)

        await session.commit()

    await message.answer(
        "🏋️‍♀️ NewFit — найди своего тренера\n\n"
        "Что хотите сделать?",
        reply_markup=get_client_main_kb(is_admin=is_admin)
    )
