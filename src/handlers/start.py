from aiogram import Router, types, F
from aiogram.filters import CommandStart
from src.keyboards.common import get_role_kb

router = Router()

@router.message(CommandStart())
@router.message(F.text == "/menu")
async def cmd_start(message: types.Message, is_admin: bool = False):
    async with SessionLocal() as session:
        user = await session.get(User, message.from_user.id)

        # If user exists and has a role, redirect to their menu
        if user and user.role:
            if user.role == UserRole.TRAINER:
                from src.keyboards.common import get_trainer_main_kb
                kb = get_trainer_main_kb(is_admin=is_admin)
                await message.answer(f"С возвращением! Личный кабинет тренера:", reply_markup=kb)
                return
            elif user.role == UserRole.CLIENT:
                from src.keyboards.common import get_client_main_kb
                kb = get_client_main_kb(is_admin=is_admin)
                await message.answer(f"С возвращением! Личный кабинет клиента:", reply_markup=kb)
                return

    # Show role selection for new users or those without a role
    await message.answer(
        "Добро пожаловать в NewFit — экосистему для фитнеса будущего! 🔥\n\n"
        "Здесь тренеры находят клиентов, а клиенты — лучших тренеров.\n\n"
        "Выберите свою роль:",
        reply_markup=get_role_kb(is_admin=is_admin)
    )

@router.message(F.text == "🛠 Админ")
async def admin_button_handler(message: types.Message):
    # This will be caught by /admin command handler in admin.py
    # but we can also trigger it manually or redirect
    from src.handlers.admin import admin_panel
    from middlewares.admin_middleware import OWNER_ID
    # Simple check, real check is in middleware
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
