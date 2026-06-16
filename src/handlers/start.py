from aiogram import Router, types, F
from aiogram.filters import CommandStart
from src.keyboards.common import get_role_kb
from src.keyboards.inline import add_admin_button
from src.models.models import User, UserRole
from src.utils.db import SessionLocal

router = Router()

@router.message(CommandStart())
@router.message(F.text == "/menu")
async def cmd_start(message: types.Message, is_admin: bool = False, effective_user_id: int = None):
    async with SessionLocal() as session:
        user = await session.get(User, effective_user_id)

        # If user exists and has a role, redirect to their menu
        if user and user.role:
            if user.role in [UserRole.TRAINER, UserRole.BEAUTY]:
                from src.keyboards.common import get_trainer_main_kb
                kb = get_trainer_main_kb(is_admin=is_admin)
                role_text = "тренера" if user.role == UserRole.TRAINER else "бьюти-мастера"
                await message.answer(f"С возвращением! Личный кабинет {role_text}:", reply_markup=kb)
                return
            elif user.role == UserRole.CLIENT:
                from src.keyboards.common import get_client_main_kb
                kb = get_client_main_kb(is_admin=is_admin)
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
        "Здесь тренеры находят клиентов, а клиенты — лучших тренеров.\n\n"
        "Выберите свою роль:",
        reply_markup=reply_markup
    )

    if is_admin:
        from src.keyboards.inline import add_admin_button
        await message.answer("🛠 Панель управления (только для админов):", reply_markup=add_admin_button(is_admin=True))

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
        "NewFit — это единая экосистема для фитнес-тренеров и клиентов в Telegram.\n"
        "Мы помогаем тренерам автоматизировать запись, а клиентам — быстро находить профессионалов."
    )

@router.message(F.text == "/help")
async def cmd_help(message: types.Message):
    await message.answer("Служба поддержки NewFit: @NewFitSupport")
