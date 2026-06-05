from aiogram import Router, F
from sqlalchemy import delete
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.models.models import Admin, User, TrainerProfile, ClientProfile
from src.utils.db import SessionLocal

router = Router()

# Состояния для FSM
from aiogram.fsm.state import State, StatesGroup
class AddAdminState(StatesGroup):
    waiting_for_id = State()

@router.message(Command("admin"))
async def admin_panel(message: Message, is_admin: bool = False):
    if not is_admin:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Добавить соадмина/тестировщика", callback_data="admin_add_user")],
        [InlineKeyboardButton(text="🎭 Войти как тренер", callback_data="admin_impersonate_trainer")],
        [InlineKeyboardButton(text="👤 Войти как клиент", callback_data="admin_impersonate_client")],
        [InlineKeyboardButton(text="🔓 Выйти из режима тестирования", callback_data="admin_stop_impersonate")],
        [InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list")],
        [InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list")],
        [InlineKeyboardButton(text="🗑 Удалить админа", callback_data="admin_remove")],
        [InlineKeyboardButton(text="🛠 Переключить тестовый режим", callback_data="admin_toggle_test")],
        [InlineKeyboardButton(text="🧹 Очистить тестовые данные", callback_data="admin_clear_test_data")],
        [InlineKeyboardButton(text="🔄 Начать с начала", callback_data="admin_start_over")],
    ])

    await message.answer("🛠 **Админ-панель NewFit**\n\nВыберите действие:", reply_markup=keyboard, parse_mode="Markdown")


@router.callback_query(F.data == "admin_add_user")
async def add_admin_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 **Добавление администратора/тестировщика**\n\n"
        "Введите Telegram ID пользователя и его роль через пробел:\n\n"
        "`ID роль`\n\n"
        "**Роли:**\n"
        "• `co_admin` — полный доступ\n"
        "• `tester_trainer` — тестирование за тренера\n"
        "• `tester_client` — тестирование за клиента\n"
        "• `tester_both` — тестирование за обе роли\n\n"
        "Пример: `123456789 tester_both`",
        parse_mode="Markdown"
    )
    await state.set_state(AddAdminState.waiting_for_id)


@router.message(AddAdminState.waiting_for_id)
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
        await callback.message.edit_text("📭 Список администраторов пуст.")
        return

    text = "📋 **Список администраторов и тестировщиков:**\n\n"
    for admin in admins:
        text += f"• `{admin.user_id}` — {admin.role}\n"

    await callback.message.edit_text(text, parse_mode="Markdown")


@router.callback_query(F.data == "admin_remove")
async def remove_admin_prompt(callback: CallbackQuery):
    await callback.message.edit_text(
        "🗑 **Удаление администратора**\n\n"
        "Введите Telegram ID пользователя, которого нужно удалить из админов:"
    )
    # TODO: добавить состояние для удаления


@router.callback_query(F.data == "admin_impersonate_trainer")
async def impersonate_trainer(callback: CallbackQuery):
    async with SessionLocal() as session:
        # Получить список тренеров
        trainers = await session.execute(
            select(User).where(User.role == "trainer")
        )
        trainers = trainers.scalars().all()

    if not trainers:
        await callback.message.edit_text("❌ Нет зарегистрированных тренеров")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{t.full_name or t.id}", callback_data=f"imp_trainer_{t.id}")]
        for t in trainers[:10]
    ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])

    await callback.message.edit_text("🎭 **Выберите тренера, под которого войти:**", reply_markup=keyboard)


@router.callback_query(F.data.startswith("imp_trainer_"))
async def do_impersonate_trainer(callback: CallbackQuery, state: FSMContext):
    trainer_id = int(callback.data.split("_")[2])

    # Сохраняем в FSM, что админ теперь работает от лица тренера
    await state.update_data(impersonate_trainer_id=trainer_id)

    await callback.message.edit_text(
        f"✅ Вы вошли как тренер ID: {trainer_id}\n\n"
        f"🔓 Нажмите «Выйти из режима тестирования» в админ-панели, чтобы вернуться."
    )


@router.callback_query(F.data == "admin_stop_impersonate")
async def stop_impersonate(callback: CallbackQuery, state: FSMContext):
    await state.update_data(impersonate_trainer_id=None, impersonate_client_id=None)
    await callback.message.edit_text("✅ Режим тестирования отключён. Вы снова в админ-панели.")


@router.callback_query(F.data == "admin_toggle_test")
async def toggle_test_mode(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_mode = data.get("is_test_mode", False)
    new_mode = not current_mode
    await state.update_data(is_test_mode=new_mode)
    status = "ВКЛЮЧЕН" if new_mode else "ВЫКЛЮЧЕН"
    await callback.answer(f"Тестовый режим {status}")
    await callback.message.answer(f"🛠 Тестовый режим теперь {status}. Новые пользователи будут помечаться как тестовые.")

@router.callback_query(F.data == "admin_clear_test_data")
async def clear_test_data(callback: CallbackQuery):
    async with SessionLocal() as session:
        # Delete users with is_test = True
        await session.execute(delete(User).where(User.is_test == True))
        await session.commit()
    await callback.message.answer("✅ Все тестовые данные удалены")
    await callback.answer()

@router.callback_query(F.data == "admin_start_over")
async def admin_start_over(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    from src.handlers.start import cmd_start
    await callback.message.delete()
    # Call cmd_start. Note: is_admin should be True since we are in admin panel
    await cmd_start(callback.message, is_admin=True)
    await callback.answer()

@router.callback_query(F.data == "admin_back")
async def back_to_admin(callback: CallbackQuery):
    # Pass False for is_admin because back_to_admin is called from callback,
    # but the middleware already verified it.
    # For now, we can just call the message handler or re-send panel.
    await callback.message.edit_text("🛠 **Админ-панель NewFit**\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👥 Добавить соадмина/тестировщика", callback_data="admin_add_user")],
            [InlineKeyboardButton(text="🎭 Войти как тренер", callback_data="admin_impersonate_trainer")],
            [InlineKeyboardButton(text="👤 Войти как клиент", callback_data="admin_impersonate_client")],
            [InlineKeyboardButton(text="🔓 Выйти из режима тестирования", callback_data="admin_stop_impersonate")],
            [InlineKeyboardButton(text="📋 Список админов", callback_data="admin_list")],
            [InlineKeyboardButton(text="🗑 Удалить админа", callback_data="admin_remove")],
            [InlineKeyboardButton(text="🛠 Переключить тестовый режим", callback_data="admin_toggle_test")],
            [InlineKeyboardButton(text="🧹 Очистить тестовые данные", callback_data="admin_clear_test_data")],
            [InlineKeyboardButton(text="🔄 Начать с начала", callback_data="admin_start_over")],
        ]),
        parse_mode="Markdown")
