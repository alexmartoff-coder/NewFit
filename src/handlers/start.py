from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from src.keyboards.common import get_role_kb, get_launch_kb
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
                from src.models.models import ClientProfile, Booking, TrainerProfile

                async with SessionLocal() as session:
                    cp_stmt = select(ClientProfile).where(ClientProfile.user_id == user.id)
                    cp = (await session.execute(cp_stmt)).scalar_one_or_none()

                    has_specialists = False
                    if cp:
                        count_stmt = select(func.count(Booking.id)).where(Booking.client_id == cp.id)
                        booking_count = (await session.execute(count_stmt)).scalar_one()
                        has_specialists = booking_count > 0

                    stmt_t = select(TrainerProfile).where(TrainerProfile.user_id == user.id)
                    has_trainer_profile = (await session.execute(stmt_t)).scalar_one_or_none() is not None

                kb = get_client_main_kb(is_admin=is_admin, has_specialists=has_specialists, is_pro=has_trainer_profile)
                await message.answer(f"С возвращением! Личный кабинет клиента:", reply_markup=kb)
                return

    # Show launch button for new users or those without a role
    welcome_text = (
        "👋 **Добро пожаловать в NewFit!**\n\n"
        "Единая экосистема для **Спортa** и **Бьюти** прямо в Telegram.\n\n"
        "• **Профессионалам:** удобное управление расписанием и привлечение клиентов.\n"
        "• **Клиентам:** быстрая запись к лучшим мастерам в пару кликов.\n\n"
        "Выберите, как вы хотите использовать бота:"
    )
    await message.answer(
        welcome_text,
        reply_markup=get_launch_kb(),
        parse_mode="Markdown"
    )


@router.message(F.text == "ℹ️ О проекте")
async def about_project_handler(message: types.Message):
    about_text = (
        "**NewFit** — это современная платформа для автоматизации записи в сферах спорта и красоты.\n\n"
        "**Что мы предлагаем:**\n"
        "• ⚡️ Мгновенное бронирование времени\n"
        "• 📅 Интерактивное расписание для мастеров\n"
        "• 📸 Портфолио с галереей работ\n"
        "• 🔔 Автоматические уведомления о записях\n\n"
        "Мы объединяем фитнес-тренеров, мастеров бьюти-индустрии и тренеров по теннису/падлу в одном удобном интерфейсе."
    )
    await message.answer(about_text, parse_mode="Markdown")

@router.message(F.text == "🚀 Запустить бота")
async def launch_bot_handler(message: types.Message, is_admin: bool = False):
    # Explicitly remove the reply keyboard and show role selection
    await message.answer(
        "Отлично! Теперь выберите вашу роль для продолжения:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await message.answer(
        "Выберите роль:",
        reply_markup=get_role_kb(is_admin=is_admin)
    )

@router.callback_query(F.data == "learn_more")
async def learn_more_callback(callback: types.CallbackQuery):
    about_text = (
        "**NewFit** — это современная платформа для автоматизации записи в сферах спорта и красоты.\n\n"
        "**Что мы предлагаем:**\n"
        "• ⚡️ Мгновенное бронирование времени\n"
        "• 📅 Интерактивное расписание для мастеров\n"
        "• 📸 Портфолио с галереей работ\n"
        "• 🔔 Автоматические уведомления о записях\n\n"
        "Мы объединяем фитнес-тренеров, мастеров бьюти-индустрии и тренеров по теннису/падлу в одном удобном интерфейсе."
    )
    await callback.message.answer(about_text, parse_mode="Markdown")
    await callback.answer()

@router.message(F.text == "🛠 Админ")
async def admin_button_handler(message: types.Message, is_admin: bool = False):
    if not is_admin:
        await message.answer("❌ У вас нет доступа к этому разделу.")
        return
    from src.handlers.admin import admin_panel
    await admin_panel(message, is_admin=True)

@router.message(F.text == "/help")
async def cmd_help(message: types.Message):
    await message.answer("Служба поддержки NewFit:\nEmail: alexandr@cbda.ru")
