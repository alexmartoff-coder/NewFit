from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from src.models.models import User, ClientProfile, UserRole, Booking
from src.utils.db import SessionLocal
from src.keyboards.common import get_client_main_kb
from src.states.client_onboarding import ClientOnboarding

router = Router()

@router.callback_query(F.data == "role_client")
@router.message(F.text == "Клиент")
@router.callback_query(F.data == "client_menu")
async def client_start(event: types.Message | types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    message = event if isinstance(event, types.Message) else event.message
    user_id = effective_user_id or event.from_user.id

    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        stmt = select(ClientProfile).where(ClientProfile.user_id == user_id)
        client_profile = (await session.execute(stmt)).scalar_one_or_none()

        # If user has a role and profile with a name, skip onboarding
        if user and user.role in [UserRole.CLIENT, UserRole.TRAINER, UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL] and client_profile and client_profile.full_name:
            count_stmt = select(func.count(Booking.id)).where(Booking.client_id == client_profile.id)
            booking_count = (await session.execute(count_stmt)).scalar_one()
            has_specialists = booking_count > 0

            text = "🏋️‍♀️ NewFit — найди своего мастера\n\nЧто хотите сделать?"
            await message.answer(text, reply_markup=get_client_main_kb(is_admin=is_admin, has_specialists=has_specialists))
            if isinstance(event, types.CallbackQuery):
                await event.answer()
            return

    await state.set_state(ClientOnboarding.full_name)
    await message.answer("Добро пожаловать в NewFit! 🎉\n\nДля продолжения, пожалуйста, введите ваши **Фамилию и Имя**:", parse_mode="Markdown")
    if isinstance(event, types.CallbackQuery):
        await event.answer()

@router.message(ClientOnboarding.full_name)
async def process_client_name(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введите и Фамилию, и Имя.")
        return

    user_id = effective_user_id or message.from_user.id

    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        if not user:
            user = User(
                id=user_id,
                username=message.from_user.username,
                full_name=full_name,
                role=UserRole.CLIENT
            )
            session.add(user)
        else:
            user.role = UserRole.CLIENT
            user.full_name = full_name

        stmt = select(ClientProfile).where(ClientProfile.user_id == user_id)
        client_profile = (await session.execute(stmt)).scalar_one_or_none()

        if not client_profile:
            client_profile = ClientProfile(
                user_id=user_id,
                full_name=full_name,
                status="active"
            )
            session.add(client_profile)
        else:
            client_profile.full_name = full_name

        await session.commit()

    await state.clear()
    # New clients definitely don't have specialists yet
    await message.answer(
        f"Приятно познакомиться, {full_name}! 👋\n\nТеперь вы можете выбирать услуги и записываться к мастерам.",
        reply_markup=get_client_main_kb(is_admin=is_admin, has_specialists=False)
    )
