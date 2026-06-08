import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.trainer_onboarding import TrainerOnboarding
from src.keyboards.common import get_format_kb, get_trainer_main_kb, get_start_reg_kb, get_spec_kb, get_city_kb, get_client_main_kb
from src.keyboards.inline import add_admin_button
from src.models.models import User, TrainerProfile, UserRole, WorkFormat, Specialization, Booking
from src.utils.db import SessionLocal
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "👨‍🏫 Я тренер")
async def trainer_start(message: types.Message, state: FSMContext, is_admin: bool = False):
    kb = get_start_reg_kb()
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer(
        "Отлично! Давайте создадим ваш профессиональный профиль в NewFit.\n\n"
        "Это займёт около 3-4 минут.\n\n"
        "Готовы начать?",
        reply_markup=kb
    )

@router.callback_query(F.data == "start_registration")
async def start_reg(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None):
    user_id = effective_user_id or callback.from_user.id
    await state.update_data(telegram_id=user_id)
    await state.set_state(TrainerOnboarding.full_name)
    await callback.message.answer("Шаг 1/9\n\nНапишите ваше ФИО:")
    await callback.answer()

@router.message(TrainerOnboarding.full_name)
async def process_name(message: types.Message, state: FSMContext, effective_user_id: int = None):
    user_id = effective_user_id or message.from_user.id
    await state.update_data(full_name=message.text, telegram_id=user_id)
    await state.set_state(TrainerOnboarding.city)
    await message.answer(
        "Шаг 2/9\n\nУкажите город работы (или \"Онлайн\", если работаете только онлайн):",
        reply_markup=get_city_kb()
    )

@router.message(TrainerOnboarding.city)
async def process_city(message: types.Message, state: FSMContext, is_admin: bool = False):
    await state.update_data(city=message.text)
    await state.set_state(TrainerOnboarding.specialization)
    await state.update_data(specializations=[])
    kb = get_spec_kb()
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer("Шаг 3/9\n\nВыберите ваши основные направления (можно несколько):", reply_markup=kb)

@router.callback_query(F.data.startswith("spec_"), TrainerOnboarding.specialization)
async def process_spec_callback(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    if callback.data == "spec_done":
        data = await state.get_data()
        if not data.get('specializations'):
            await callback.answer("Выберите хотя бы одно направление!")
            return
        await state.set_state(TrainerOnboarding.experience)
        await callback.message.answer("Шаг 4/9\n\nСколько лет опыта в фитнесе?")
        await callback.answer()
        return

    spec_map = {
        "spec_strength": "Силовые тренировки",
        "spec_weight_loss": "Похудение и жиросжигание",
        "spec_func": "Функциональный тренинг",
        "spec_rehab": "Реабилитация и ОФП",
        "spec_crossfit": "Кроссфит / HIIT",
        "spec_gender": "Тренировки для женщин/мужчин",
        "spec_teens": "Работа с подростками",
        "spec_other": "Другое"
    }

    spec = spec_map.get(callback.data)
    if spec:
        data = await state.get_data()
        specs = data.get('specializations', [])
        if spec in specs:
            specs.remove(spec)
            await callback.answer(f"Удалено: {spec}")
        else:
            specs.append(spec)
            await callback.answer(f"Добавлено: {spec}")
        await state.update_data(specializations=specs)

        # Update keyboard to show checkmarks
        kb = get_spec_kb(selected_specs=specs)
        await callback.message.edit_reply_markup(reply_markup=kb)

    await callback.answer()

@router.message(TrainerOnboarding.experience)
async def process_experience(message: types.Message, state: FSMContext, is_admin: bool = False):
    try:
        # Enforce numeric input for experience since the DB column is now Integer
        exp = int(message.text)
        await state.update_data(experience=exp)
        await state.set_state(TrainerOnboarding.formats)
        kb = get_format_kb()
        kb = add_admin_button(kb, is_admin=is_admin)
        await message.answer("Шаг 5/9\n\nКакие форматы вы предлагаете?", reply_markup=kb)
    except ValueError:
        await message.answer("Пожалуйста, введите число (количество полных лет опыта).")

@router.callback_query(F.data.startswith("fmt_"), TrainerOnboarding.formats)
async def process_formats_callback(callback: types.CallbackQuery, state: FSMContext):
    fmt_map = {
        "fmt_offline": WorkFormat.OFFLINE,
        "fmt_online": WorkFormat.ONLINE,
        "fmt_hybrid": WorkFormat.HYBRID
    }
    work_format = fmt_map.get(callback.data)
    await state.update_data(work_format=work_format)
    await state.set_state(TrainerOnboarding.price_single)
    await callback.message.answer("Шаг 6/9\n\nУкажите вашу цену за разовое занятие (в ₽):")
    await callback.answer()

@router.message(TrainerOnboarding.price_single)
async def process_price_single(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price_single=price)
        await state.set_state(TrainerOnboarding.price_package)
        await message.answer("Шаг 7/9\n\nУкажите цену за абонемент на 12 занятий (в ₽):")
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@router.message(TrainerOnboarding.price_package)
async def process_price_package(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price_package=price)
        await state.set_state(TrainerOnboarding.photo)
        await message.answer("Шаг 8/9\n\nЗагрузите ваше фото в хорошем качестве (портрет):", reply_markup=types.ReplyKeyboardRemove())
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@router.message(TrainerOnboarding.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext, is_admin: bool = False):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_url=photo_id)
    await state.set_state(TrainerOnboarding.video)
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[[types.InlineKeyboardButton(text="Пропустить", callback_data="skip_video")]]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer(
        "Шаг 9/9\n\nЗагрузите короткое видео-презентацию (15–60 секунд).\n"
        "Это очень важно для клиентов! Вы также можете пропустить этот шаг.",
        reply_markup=kb
    )

@router.callback_query(F.data == "skip_video", TrainerOnboarding.video)
async def skip_video(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    await callback.answer("Видео пропущено.")
    # Remove reply markup to avoid double clicking
    await callback.message.edit_reply_markup(reply_markup=None)
    user_id = effective_user_id or callback.from_user.id
    await finish_onboarding(callback.message, state, user_id, callback.from_user.username, is_admin)

@router.message(TrainerOnboarding.video, F.video)
async def process_video(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    video_id = message.video.file_id
    await state.update_data(video_url=video_id)
    user_id = effective_user_id or message.from_user.id
    await finish_onboarding(message, state, user_id, message.from_user.username, is_admin)

async def finish_onboarding(message: types.Message, state: FSMContext, user_id: int, username: str, is_admin: bool = False):
    try:
        data = await state.get_data()

        # Priority for user_id: state (mock) > effective_user_id > message.from_user.id
        user_id = data.get('telegram_id', user_id)

        photo_url = data.get('photo_url')
        video_url = data.get('video_url')

        # Тестовый режим — удаляем старый профиль, чтобы можно было тестировать с одного аккаунта
        test_mode = data.get("is_test_mode", False) or is_admin

        async with SessionLocal() as session:
            logger.info(f"Starting finish_onboarding for user {user_id} (test_mode={test_mode})")

            # === 1. User ===
            user = await session.get(User, user_id)
            if not user:
                user = User(
                    id=user_id,
                    username=username,
                    full_name=data.get('full_name', 'Не указано'),
                    role=UserRole.TRAINER,
                    is_test=data.get("is_test_mode", False)
                )
                session.add(user)
            else:
                user.role = UserRole.TRAINER
                user.full_name = data.get('full_name', user.full_name)
                user.username = username or user.username

            await session.flush()

            # === 2. TrainerProfile — безопасное удаление для тестов
            if test_mode:
                try:
                    # Удаляем связанные записи, чтобы избежать ForeignKeyViolation
                    await session.execute(
                        delete(Booking).where(Booking.trainer_id == user_id)
                    )
                    await session.execute(
                        delete(TrainerProfile).where(TrainerProfile.user_id == user_id)
                    )
                    logger.info(f"Test mode: очищен старый профиль тренера {user_id}")
                except Exception as clean_error:
                    logger.warning(f"Не удалось очистить старые данные: {clean_error}")
                    # Продолжаем — будем обновлять существующий профиль

            # Создаём / обновляем профиль
            stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id).options(selectinload(TrainerProfile.specializations))
            res = await session.execute(stmt)
            trainer_profile = res.scalar_one_or_none()

            if not trainer_profile:
                trainer_profile = TrainerProfile(
                    user_id=user_id,
                    city=data.get('city', 'Не указан'),
                    experience=int(data.get('experience', 0)),
                    work_format=data.get('work_format', WorkFormat.ONLINE),
                    price_single=float(data.get('price_single', 0)),
                    price_package=float(data.get('price_package', 0)),
                    photo_url=photo_url,
                    video_presentation_url=video_url,
                    status="approved",
                    rating=5.0,
                    is_premium=False,
                    specializations=[]
                )
                session.add(trainer_profile)
                logger.info(f"Создан новый профиль тренера для user {user_id}")
            else:
                trainer_profile.city = data.get('city', trainer_profile.city)
                trainer_profile.experience = int(data.get('experience', trainer_profile.experience))
                trainer_profile.work_format = data.get('work_format', trainer_profile.work_format)
                trainer_profile.price_single = float(data.get('price_single', trainer_profile.price_single))
                trainer_profile.price_package = float(data.get('price_package', trainer_profile.price_package))
                if photo_url:
                    trainer_profile.photo_url = photo_url
                if video_url:
                    trainer_profile.video_presentation_url = video_url
                trainer_profile.status = "approved"
                logger.info(f"Обновлён профиль тренера {user_id}")

            # Flush to get the trainer_profile.id if it's new, required for specializations association
            await session.flush()

            # === 3. Specializations ===
            if data.get('specializations'):
                spec_stmt = select(Specialization).where(Specialization.name.in_(data['specializations']))
                spec_res = await session.execute(spec_stmt)
                trainer_profile.specializations = list(spec_res.scalars().all())
                logger.info(f"Linked {len(trainer_profile.specializations)} specializations for trainer {user_id}")

            await session.commit()
            logger.info(f"Регистрация тренера {user_id} завершена успешно")

        await state.clear()

        await message.answer(
            "Поздравляем! 🎉\n\n"
            "Ваш профиль успешно создан и отправлен на модерацию.\n\n"
            "Вы уже можете пользоваться кабинетом тренера.",
            reply_markup=get_trainer_main_kb(is_admin=is_admin)
        )

    except Exception as e:
        logger.exception("Error in finish_onboarding")
        await message.answer("❌ Ошибка при сохранении профиля. Попробуйте ещё раз или напишите в поддержку.")
