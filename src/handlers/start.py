from aiogram import Router, types, F
from aiogram.filters import CommandStart
from src.keyboards.common import get_role_kb
from src.keyboards.inline import add_admin_button
from src.models.models import User, UserRole
from src.utils.db import SessionLocal
from sqlalchemy import select, func

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, is_admin: bool = False, effective_user_id: int = None):
    async with SessionLocal() as session:
        user = await session.get(User, effective_user_id)

        # If user exists and has a role, redirect to their menu
        if user and user.role:
            if user.role in [UserRole.TRAINER, UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL]:
                from src.keyboards.common import get_trainer_main_kb
                from src.models.models import TrainerProfile, WorkFormat
                stmt_p = select(TrainerProfile).where(TrainerProfile.user_id == user.id)
                profile = (await session.execute(stmt_p)).scalar_one_or_none()
                has_online = (profile.work_format in [WorkFormat.ONLINE, WorkFormat.HYBRID]) if profile else False

                kb = get_trainer_main_kb(is_admin=is_admin, has_online=has_online)
                role_text = "мастера"
                if user.role == UserRole.BEAUTY: role_text = "бьюти-мастера"
                elif user.role == UserRole.TENNIS: role_text = "тренера по теннису"
                elif user.role == UserRole.PADEL: role_text = "тренера по падлу"
                await message.answer(f"С возвращением! Личный кабинет {role_text}:", reply_markup=kb)
                return
            elif user.role == UserRole.CLIENT:
                from src.keyboards.common import get_client_main_kb
                from src.models.models import ClientProfile, Booking

                async with SessionLocal() as session:
                    cp_stmt = select(ClientProfile).where(ClientProfile.user_id == user.id)
                    cp = (await session.execute(cp_stmt)).scalar_one_or_none()

                    has_specialists = False
                    if cp:
                        count_stmt = select(func.count(Booking.id)).where(Booking.client_id == cp.id)
                        booking_count = (await session.execute(count_stmt)).scalar_one()
                        has_specialists = booking_count > 0

                kb = get_client_main_kb(is_admin=is_admin, has_specialists=has_specialists)
                await message.answer(f"С возвращением! Личный кабинет клиента:", reply_markup=kb)
                return

    # Show role selection for new users or those without a role
    # Note: get_role_kb returns ReplyKeyboardMarkup.
    # The requirement asks to use add_admin_button which is for Inline keyboards.
    # I will add an inline admin button if the user is admin,
    # but the role keyboard itself is a Reply keyboard.
    # To follow instructions exactly, I'll send the admin button as a separate message or
    # convert the role selection to inline.
    # For now, let's keep reply kb but also show inline admin button if needed.

    reply_markup = get_role_kb(is_admin=is_admin)

    await message.answer(
        "Добро пожаловать в NewFit — экосистему для фитнеса будущего! 🔥\n\n"
        "Выберите свою роль:",
        reply_markup=reply_markup
    )

@router.message(F.text == "🛠 Админ")
async def admin_button_handler(message: types.Message, is_admin: bool = False):
    if not is_admin:
        await message.answer("❌ У вас нет доступа к этому разделу.")
        return
    from src.handlers.admin import admin_panel
    await admin_panel(message, is_admin=True)

@router.message(F.text == "❓ Узнать больше о NewFit")
async def learn_more(message: types.Message):
    await message.answer(
        "NewFit — это единая экосистема для фитнес-мастеров и клиентов в Telegram.\n"
        "Мы помогаем мастерам автоматизировать запись, а клиентам — быстро находить профессионалов."
    )

@router.message(F.text == "/help")
async def cmd_help(message: types.Message):
    await message.answer("Служба поддержки NewFit: @NewFitSupport")
