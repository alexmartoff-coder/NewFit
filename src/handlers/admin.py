from aiogram import Router, F
from sqlalchemy import delete
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.models import Admin, User, TrainerProfile, ClientProfile
from src.utils.db import SessionLocal

import random
import logging
from src.states.trainer_onboarding import TrainerOnboarding

router = Router()
logger = logging.getLogger(__name__)

# Состояния для FSM
from aiogram.fsm.state import State, StatesGroup
class AdminStates(StatesGroup):
    waiting_for_admin_id = State()
    waiting_for_impersonate_trainer_id = State()
    waiting_for_impersonate_client_id = State()
    waiting_for_remove_admin_id = State()
    confirm_remove_admin = State()

@router.callback_query(F.data == "admin_panel")
async def admin_button_handler(callback: CallbackQuery, is_admin: bool = False):
    """Вызывает админ-панель при нажатии кнопки Админ"""
    if not is_admin:
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    await admin_panel(callback.message, is_admin=True)
    await callback.answer()

@router.message(Command("admin"))
async def admin_panel(message: Message, is_admin: bool = False):
    if not is_admin:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Добавить соадмина", callback_data="admin_add_user")],
        [InlineKeyboardButton(text="🎭 Войти как профи", callback_data="admin_impersonate_trainer")],
        [InlineKeyboardButton(text="👤 Войти как клиент", callback_data="admin_impersonate_client")],
        [InlineKeyboardButton(text="🔓 Выйти из режима входа", callback_data="admin_stop_impersonate")],
        [InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list")],
        [InlineKeyboardButton(text="🗑 Удалить админа", callback_data="admin_remove")],
        [InlineKeyboardButton(text="🔥 Удалить пользователей", callback_data="admin_delete_all_users")],
        [InlineKeyboardButton(text="🔄 Начать с начала", callback_data="admin_start_over")],
    ])

    await message.answer("🛠 **Админ-панель NewFit**\n\nВыберите действие:", reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "admin_add_user")
async def add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    text = (
        "📝 **Добавление администратора**\n\n"
        "Введите Telegram ID пользователя и его роль через пробел:\n\n"
        "`ID роль`\n\n"
        "**Роли:**\n"
        "• `co_admin` — полный доступ\n"
        "• `tester_trainer` — тестирование за мастера\n"
        "• `tester_client` — тестирование за клиента\n"
        "• `tester_both` — тестирование за обе роли\n\n"
        "Пример: `123456789 co_admin`"
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_admin_id)

async def _legacy_add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 **Добавление администратора**\n\n"
        "Введите Telegram ID пользователя и его роль через пробел:\n\n"
        "`ID роль`\n\n"
        "**Роли:**\n"
        "• `co_admin` — полный доступ\n"
        "• `tester_trainer` — тестирование за мастера\n"
        "• `tester_client` — тестирование за клиента\n"
        "• `tester_both` — тестирование за обе роли\n\n"
        "Пример: `123456789 co_admin`",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_admin_id)


@router.message(AdminStates.waiting_for_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.answer("❌ Неверный формат. Используйте: `ID роль`")
            return

        user_id = int(parts[0])
        role = parts[1]

        async with SessionLocal() as session:
            # Проверяем, существует ли пользователь в БД
            user = await session.execute(select(User).where(User.id == user_id))
            user = user.scalar_one_or_none()

            if not user:
                await message.answer(f"❌ Пользователь с ID {user_id} не найден в базе данных. Попросите его нажать /start в боте.")
                return

            # Определяем права
            can_test_trainer = role in ["tester_trainer", "tester_both"]
            can_test_client = role in ["tester_client", "tester_both"]
            is_co_admin = role == "co_admin"

            if is_co_admin:
                can_test_trainer = True
                can_test_client = True

            # Создаём запись админа
            admin = Admin(
                user_id=user_id,
                role=role,
                added_by=message.from_user.id,
                can_test_trainer=can_test_trainer,
                can_test_client=can_test_client
            )
            session.add(admin)
            await session.commit()

        await message.answer(f"✅ Пользователь {user_id} добавлен как `{role}`")

    except ValueError:
        await message.answer("❌ ID должен быть числом")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

    await state.clear()


@router.callback_query(F.data == "admin_list")
async def list_admins(callback: CallbackQuery):
    async with SessionLocal() as session:
        admins = await session.execute(select(Admin))
        admins = admins.scalars().all()

    if not admins:
        text = "📭 Список администраторов пуст."
        if callback.message.photo:
            await callback.message.edit_caption(caption=text)
        else:
            await callback.message.edit_text(text)
        return

    text = "📋 **Список администраторов и тестировщиков:**\n\n"
    for admin in admins:
        text += f"• `{admin.user_id}` — {admin.role}\n"

    if callback.message.photo:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, parse_mode="Markdown")


@router.callback_query(F.data == "admin_remove")
async def remove_admin_prompt(callback: CallbackQuery, state: FSMContext):
    text = (
        "🗑 **Удаление администратора**\n\n"
        "Введите Telegram ID пользователя, которого нужно удалить из админов:"
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await state.set_state(AdminStates.waiting_for_remove_admin_id)

@router.message(AdminStates.waiting_for_remove_admin_id)
async def process_remove_admin_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        async with SessionLocal() as session:
            admin = await session.execute(select(Admin).where(Admin.user_id == user_id))
            admin = admin.scalar_one_or_none()

            if not admin:
                await message.answer(f"❌ Администратор с ID {user_id} не найден.")
                await state.clear()
                return

            await state.update_data(admin_id_to_remove=user_id)
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑 Удалить?", callback_data="admin_confirm_remove")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_panel")]
            ])
            await message.answer(f"Вы уверены, что хотите удалить администратора `{user_id}`?", reply_markup=kb, parse_mode="Markdown")
            await state.set_state(AdminStates.confirm_remove_admin)

    except ValueError:
        await message.answer("❌ ID должен быть числом")

@router.callback_query(F.data == "admin_confirm_remove", AdminStates.confirm_remove_admin)
async def confirm_remove_admin(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("admin_id_to_remove")

    async with SessionLocal() as session:
        await session.execute(delete(Admin).where(Admin.user_id == user_id))
        await session.commit()

    text = f"✅ Администратор `{user_id}` удалён."
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, parse_mode="Markdown")
    await state.clear()
    await admin_panel(callback.message, is_admin=True)

@router.callback_query(F.data == "admin_impersonate_trainer")
async def impersonate_trainer_prompt(callback: CallbackQuery, state: FSMContext):
    text = "🎭 **Войти как профи**\n\nВведите Telegram ID мастера:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await state.set_state(AdminStates.waiting_for_impersonate_trainer_id)

@router.message(AdminStates.waiting_for_impersonate_trainer_id)
async def process_imp_trainer(message: Message, state: FSMContext):
    try:
        trainer_id = int(message.text.strip())
        await state.update_data(impersonate_trainer_id=trainer_id, impersonate_client_id=None)
        await message.answer(
            f"✅ Вы вошли как профи ID: `{trainer_id}`\n\n"
            f"🔓 Используйте админ-панель, чтобы выйти.",
            parse_mode="Markdown"
        )
        await state.set_state(None) # Clear specific state but keep data

        # Immediate redirection to the menu
        from src.keyboards.common import get_trainer_main_kb
        await message.answer("Переход в кабинет мастера...", reply_markup=get_trainer_main_kb(is_admin=True))
        await admin_panel(message, is_admin=True)
    except ValueError:
        await message.answer("❌ ID должен быть числом")

@router.callback_query(F.data == "admin_impersonate_client")
async def impersonate_client_prompt(callback: CallbackQuery, state: FSMContext):
    text = "👤 **Войти как клиент**\n\nВведите Telegram ID клиента:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await state.set_state(AdminStates.waiting_for_impersonate_client_id)

@router.message(AdminStates.waiting_for_impersonate_client_id)
async def process_imp_client(message: Message, state: FSMContext):
    try:
        client_id = int(message.text.strip())
        await state.update_data(impersonate_client_id=client_id, impersonate_trainer_id=None)
        await message.answer(
            f"✅ Вы вошли как клиент ID: `{client_id}`\n\n"
            f"🔓 Используйте админ-панель, чтобы выйти.",
            parse_mode="Markdown"
        )
        await state.set_state(None)

        # Immediate redirection to the menu
        from src.keyboards.common import get_client_main_kb
        await message.answer("Переход в кабинет клиента...", reply_markup=get_client_main_kb(is_admin=True))
        await admin_panel(message, is_admin=True)
    except ValueError:
        await message.answer("❌ ID должен быть числом")

@router.callback_query(F.data == "admin_stop_impersonate")
async def stop_impersonate(callback: CallbackQuery, state: FSMContext):
    await state.update_data(impersonate_trainer_id=None, impersonate_client_id=None)
    text = "✅ Режим входа отключён. Вы снова в админ-панели."
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)

    # Restore admin's own menu
    from src.keyboards.common import get_role_kb
    await callback.message.answer("Режим тестирования завершен. Выберите роль:", reply_markup=get_role_kb(is_admin=True))


@router.callback_query(F.data == "admin_start_over")
async def admin_start_over(callback: CallbackQuery, state: FSMContext):
    # Очищаем состояние FSM (если было)
    await state.clear()

    from src.keyboards.common import get_role_kb

    await callback.message.delete()  # удаляем сообщение с админ-панелью
    await callback.message.answer(
        "🔄 Перезапуск бота...\n\n"
        "Добро пожаловать в NewFit — экосистему для фитнеса будущего! 🔥\n\n"
        "Выберите свою роль:",
        reply_markup=get_role_kb(is_admin=True)
    )
    await callback.answer()

@router.callback_query(F.data == "admin_delete_all_users")
async def delete_users_prompt(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 ДА, УДАЛИТЬ ВСЕХ (кроме админов)", callback_data="admin_confirm_delete_all")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_panel")]
    ])
    await callback.message.edit_text(
        "⚠️ **ВНИМАНИЕ**\n\n"
        "Это действие удалит ВСЕХ пользователей (мастеров, клиентов, бьюти) и их данные (слоты, записи, профили).\n\n"
        "Администраторы останутся. Вы уверены?",
        reply_markup=kb,
        parse_mode="Markdown"
    )

from sqlalchemy import text

@router.callback_query(F.data == "admin_confirm_delete_all")
async def confirm_delete_all(callback: CallbackQuery):
    async with SessionLocal() as session:
        # 1. Identify admins to preserve (as tuple for the query)
        admin_stmt = select(Admin.user_id)
        admin_res = await session.execute(admin_stmt)
        admin_ids = list(admin_res.scalars().all())
        if callback.from_user.id not in admin_ids:
            admin_ids.append(callback.from_user.id)
        admin_ids_tuple = tuple(admin_ids)

        try:
            # 2. Powerful cleanup using TRUNCATE CASCADE
            # This handles all FK dependencies automatically and resets sequences.
            tables = [
                "reminders", "bookings", "reviews", "subscriptions", "time_slots",
                "trainer_specializations", "trainer_schedules", "schedule_templates",
                "trainer_profiles", "client_profiles"
            ]

            logger.info(f"Admin {callback.from_user.id}: Starting TRUNCATE CASCADE. Preserving: {admin_ids_tuple}")

            # Reset identity resets SERIAL/IDENTITY columns
            tables_str = ", ".join(tables)
            await session.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE"))

            # 3. Delete non-admin users from 'users' table
            logger.info("Admin: Deleting non-admin users from 'users' table")
            await session.execute(
                text("DELETE FROM users WHERE id NOT IN :admin_ids"),
                {"admin_ids": admin_ids_tuple}
            )

            await session.commit()
            logger.info("Admin: Bulk delete successful.")
            await callback.message.edit_text("✅ Все не-админ пользователи и их данные удалены. База очищена.")

        except Exception as e:
            await session.rollback()
            logger.warning(f"Admin: TRUNCATE CASCADE failed, falling back to manual DELETE: {e}")

            # 4. Fallback to ordered DELETE if TRUNCATE is not supported (e.g. SQLite)
            try:
                for table in reversed(tables): # Start with leaf tables
                    await session.execute(text(f"DELETE FROM {table}"))

                await session.execute(
                    text("DELETE FROM users WHERE id NOT IN :admin_ids"),
                    {"admin_ids": admin_ids_tuple}
                )
                await session.commit()
                await callback.message.edit_text("✅ Все данные удалены (через ручной режим).")
            except Exception as e2:
                await session.rollback()
                logger.exception("Admin: Critical error during fallback delete")
                await callback.message.answer(f"❌ Ошибка при очистке базы: {e2}")
                return

    await admin_panel(callback.message, is_admin=True)

@router.callback_query(F.data == "admin_back")
async def back_to_admin(callback: CallbackQuery):
    await admin_panel(callback.message, is_admin=True)
