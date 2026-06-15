from aiogram import Router, types, F
from sqlalchemy import select
from src.models.models import User, ClientProfile, UserRole
from src.utils.db import SessionLocal
from src.keyboards.common import get_client_main_kb

router = Router()

@router.message(F.text == "🏋️‍♀️ Я клиент")
@router.callback_query(F.data == "client_menu")
async def client_start(event: types.Message | types.CallbackQuery, is_admin: bool = False, effective_user_id: int = None):
    message = event if isinstance(event, types.Message) else event.message
    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            user = User(
                id=user_id,
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
            client_profile = ClientProfile(
                user_id=user.id,
                full_name=user.full_name,
                status="active"
            )
            session.add(client_profile)

        await session.commit()

    text = (
        "🏋️‍♀️ NewFit — найди своего тренера\n\n"
        "Что хотите сделать?"
    )
    if isinstance(event, types.CallbackQuery):
        await message.answer(text, reply_markup=get_client_main_kb(is_admin=is_admin))
        await event.answer()
    else:
        await message.answer(text, reply_markup=get_client_main_kb(is_admin=is_admin))
