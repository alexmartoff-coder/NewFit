from aiogram import Router, types, F
from src.models.models import User, ClientProfile, UserRole
from src.utils.db import SessionLocal

router = Router()

@router.message(F.text == "Я клиент")
async def client_start(message: types.Message):
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

        client_profile = await session.get(ClientProfile, user.id)
        if not client_profile:
            client_profile = ClientProfile(user_id=user.id)
            session.add(client_profile)

        await session.commit()

    await message.answer("Добро пожаловать, клиент! Теперь вы можете искать тренеров.")
