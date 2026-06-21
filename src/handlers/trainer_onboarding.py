import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.trainer_onboarding import TrainerOnboarding
from src.keyboards.common import get_format_kb, get_trainer_main_kb, get_start_reg_kb, get_spec_kb, get_city_kb, get_client_main_kb
from src.keyboards.inline import add_admin_button
from src.models.models import User, TrainerProfile, UserRole, WorkFormat, Specialization, Booking
from src.utils.db import SessionLocal
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "Тренер")
@router.message(F.text == "Бьюти")
async def provider_start(message: types.Message, state: FSMContext, is_admin: bool = False):
    role = UserRole.TRAINER if "тренер" in message.text.lower() else UserRole.BEAUTY
    await state.update_data(role=role)
    kb = get_start_reg_kb()
    kb = add_admin_button(kb, is_admin=is_admin)

    role_text = "профессиональный профиль" if role == UserRole.TRAINER else "профиль бьюти-мастера"

    await message.answer(
        f"Отлично! Давайте создадим ваш {role_text} в NewFit.\n\n"
        "Это займёт около 3-4 минут.\n\n"
        "Готовы начать?",
        reply_markup=kb
    )

@router.callback_query(F.data == "start_registration")
async def start_reg(callback: types.CallbackQuery, state: FSMContext, effective_user_id: int = None, is_admin: bool = False):
    user_id = effective_user_id or callback.from_user.id
    await state.update_data(telegram_id=user_id)
    await state.set_state(TrainerOnboarding.full_name)

    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        kb = None
        if user and user.full_name:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"Не менять ({user.full_name})", callback_data="skip_step")]
            ])
            kb = add_admin_button(kb, is_admin=is_admin)

    await callback.message.answer("Шаг 1/9\n\nНапишите ваше ФИО:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "skip_step")
async def skip_step_handler(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    current_state = await state.get_state()
    user_id = effective_user_id or callback.from_user.id

    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id).options(selectinload(TrainerProfile.specializations))
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        if current_state == TrainerOnboarding.full_name:
            # full_name is already in 'user' object, but we'll re-set it in state for consistency
            await state.update_data(full_name=user.full_name)
            await state.set_state(TrainerOnboarding.city)
            kb = get_city_kb()
            if profile and profile.city:
                # Add skip button to city keyboard
                skip_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"Не менять ({profile.city})", callback_data="skip_step")]
                ])
                await callback.message.answer(f"Шаг 2/9\n\nУкажите город работы:", reply_markup=kb)
                await callback.message.answer("Или нажмите кнопку ниже, чтобы не менять:", reply_markup=add_admin_button(skip_kb, is_admin=is_admin))
            else:
                await callback.message.answer(f"Шаг 2/9\n\nУкажите город работы:", reply_markup=kb)

        elif current_state == TrainerOnboarding.city:
            await state.update_data(city=profile.city)
            await state.set_state(TrainerOnboarding.specialization)
            await state.update_data(specializations=[s.name for s in profile.specializations])
            data = await state.get_data()
            kb = get_spec_kb(selected_specs=[s.name for s in profile.specializations], role=data.get('role', 'TRAINER'))
            await callback.message.answer("Шаг 3/9\n\nВыберите ваши основные направления:", reply_markup=add_admin_button(kb, is_admin=is_admin))

        elif current_state == TrainerOnboarding.experience:
            await state.update_data(experience=profile.experience)
            data = await state.get_data()
            if data.get('role') == UserRole.BEAUTY:
                await state.update_data(work_format=WorkFormat.OFFLINE)
                await state.set_state(TrainerOnboarding.price_services)
                specs = data.get('specializations', [])
                if specs:
                    await state.update_data(remaining_specs=specs.copy(), service_prices=profile.service_prices or {})
                    first_spec = specs[0]
                    await callback.message.answer(f"Шаг 6/9\n\nУкажите цену за услугу «{first_spec}» (в ₽):")
                else:
                    await state.set_state(TrainerOnboarding.price_package)
                    await callback.message.answer("Шаг 7/9\n\nУкажите цену за пакет услуг (в ₽):")
            else:
                await state.set_state(TrainerOnboarding.formats)
                kb = get_format_kb()
                skip_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"Не менять ({profile.experience} лет)", callback_data="skip_step")]
                ])
                await callback.message.answer("Шаг 5/9\n\nКакие форматы вы предлагаете?", reply_markup=add_admin_button(kb, is_admin=is_admin))
                await callback.message.answer("Или нажмите, чтобы не менять:", reply_markup=skip_kb)

        elif current_state == TrainerOnboarding.price_single:
            await state.update_data(price_single=profile.price_single)
            await state.set_state(TrainerOnboarding.price_package)
            skip_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"Не менять ({profile.price_single}₽)", callback_data="skip_step")]
            ])
            await callback.message.answer("Шаг 7/9\n\nУкажите цену за абонемент на 12 занятий (в ₽):", reply_markup=add_admin_button(skip_kb, is_admin=is_admin))

        elif current_state == TrainerOnboarding.price_package:
            await state.update_data(price_package=profile.price_package)
            await state.set_state(TrainerOnboarding.photo)
            skip_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"Не менять фото", callback_data="skip_step")]
            ])
            await callback.message.answer("Шаг 8/9\n\nЗагрузите ваше фото или оставьте прежнее:", reply_markup=add_admin_button(skip_kb, is_admin=is_admin))

        elif current_state == TrainerOnboarding.photo:
            await state.update_data(photo_url=profile.photo_url)
            await state.set_state(TrainerOnboarding.video)
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Пропустить", callback_data="skip_video")],
                [types.InlineKeyboardButton(text="Не менять видео", callback_data="skip_step")]
            ])
            await callback.message.answer("Шаг 9/9\n\nЗагрузите видео-презентацию:", reply_markup=add_admin_button(kb, is_admin=is_admin))

    await callback.answer()

@router.message(TrainerOnboarding.full_name)
async def process_name(message: types.Message, state: FSMContext, effective_user_id: int = None, is_admin: bool = False):
    user_id = effective_user_id or message.from_user.id
    await state.update_data(full_name=message.text, telegram_id=user_id)
    await state.set_state(TrainerOnboarding.city)

    async with SessionLocal() as session:
        stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        kb = get_city_kb()
        if profile and profile.city:
            skip_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"Не менять ({profile.city})", callback_data="skip_step")]
            ])
            await message.answer("Шаг 2/9\n\nУкажите город работы:", reply_markup=kb)
            await message.answer("Или не менять:", reply_markup=add_admin_button(skip_kb, is_admin=is_admin))
        else:
            await message.answer("Шаг 2/9\n\nУкажите город работы:", reply_markup=kb)

@router.message(TrainerOnboarding.city)
async def process_city(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    city = message.text.strip()
    await state.update_data(city=city)
    await state.set_state(TrainerOnboarding.specialization)

    user_id = effective_user_id or message.from_user.id
    async with SessionLocal() as session:
        stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id).options(selectinload(TrainerProfile.specializations))
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        specs = [s.name for s in profile.specializations] if profile else []
        await state.update_data(specializations=specs)
        data = await state.get_data()
        kb = get_spec_kb(selected_specs=specs, role=data.get('role', 'TRAINER'))
        await message.answer("Шаг 3/9\n\nВыберите ваши основные направления:", reply_markup=add_admin_button(kb, is_admin=is_admin))

@router.callback_query(F.data.startswith("spec_"), TrainerOnboarding.specialization)
async def process_spec_callback(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    if callback.data == "spec_done":
        data = await state.get_data()
        if not data.get('specializations'):
            await callback.answer("Выберите хотя бы одно направление!")
            return

        user_id = effective_user_id or callback.from_user.id
        await state.set_state(TrainerOnboarding.experience)

        async with SessionLocal() as session:
            stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            res = await session.execute(stmt)
            profile = res.scalar_one_or_none()

            kb = None
            if profile and profile.experience is not None:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"Не менять ({profile.experience} лет)", callback_data="skip_step")]
                ])
                kb = add_admin_button(kb, is_admin=is_admin)

            await callback.message.answer("Шаг 4/9\n\nСколько лет опыта в фитнесе?", reply_markup=kb)
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

    beauty_map = {
        "spec_manicure": "Маникюр",
        "spec_pedicure": "Педикюр",
        "spec_massage": "Массаж",
        "spec_cosmetology": "Косметология",
        "spec_hair": "Парикмахерские услуги",
        "spec_brows": "Брови и ресницы",
        "spec_makeup": "Макияж",
        "spec_other": "Другое"
    }

    spec = spec_map.get(callback.data) or beauty_map.get(callback.data)
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
        kb = get_spec_kb(selected_specs=specs, role=data.get('role', 'TRAINER'))
        await callback.message.edit_reply_markup(reply_markup=add_admin_button(kb, is_admin=is_admin))

    await callback.answer()

@router.message(TrainerOnboarding.experience)
async def process_experience(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    try:
        exp = int(message.text)
        await state.update_data(experience=exp)
        data = await state.get_data()
        role = data.get('role')

        if role == UserRole.BEAUTY:
            # Skip formats (Step 5) for Beauty role
            await state.update_data(work_format=WorkFormat.OFFLINE) # Default to offline for beauty
            await state.set_state(TrainerOnboarding.price_services)
            specs = data.get('specializations', [])
            if specs:
                await state.update_data(remaining_specs=specs.copy(), service_prices={})
                first_spec = specs[0]
                await message.answer(f"Шаг 6/9\n\nУкажите цену за услугу «{first_spec}» (в ₽):")
            else:
                await state.set_state(TrainerOnboarding.price_package)
                await message.answer("Шаг 7/9\n\nУкажите цену за пакет услуг (в ₽):")
        else:
            await state.set_state(TrainerOnboarding.formats)
            user_id = effective_user_id or message.from_user.id
            async with SessionLocal() as session:
                stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
                res = await session.execute(stmt)
                profile = res.scalar_one_or_none()

                kb = get_format_kb()
                await message.answer("Шаг 5/9\n\nКакие форматы вы предлагаете?", reply_markup=add_admin_button(kb, is_admin=is_admin))

                if profile and profile.work_format:
                    skip_kb = types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text=f"Не менять ({profile.work_format})", callback_data="fmt_" + str(profile.work_format).lower())]
                    ])
                    await message.answer("Или не менять:", reply_markup=skip_kb)

    except ValueError:
        await message.answer("Пожалуйста, введите число (количество полных лет опыта).")

@router.callback_query(F.data.startswith("fmt_"), TrainerOnboarding.formats)
async def process_formats_callback(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    fmt_map = {
        "fmt_offline": WorkFormat.OFFLINE,
        "fmt_online": WorkFormat.ONLINE,
        "fmt_hybrid": WorkFormat.HYBRID
    }
    work_format = fmt_map.get(callback.data)
    await state.update_data(work_format=work_format)
    await state.set_state(TrainerOnboarding.price_single)

    user_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
        stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()

        kb = None
        if profile and profile.price_single:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=f"Не менять ({profile.price_single}₽)", callback_data="skip_step")]
            ])
            kb = add_admin_button(kb, is_admin=is_admin)

        await callback.message.answer("Шаг 6/9\n\nУкажите вашу цену за разовое занятие (в ₽):", reply_markup=kb)
    await callback.answer()

@router.message(TrainerOnboarding.price_services)
async def process_price_services(message: types.Message, state: FSMContext, is_admin: bool = False):
    try:
        price = float(message.text)
        data = await state.get_data()
        remaining_specs = data.get('remaining_specs', [])
        service_prices = data.get('service_prices', {})

        current_spec = remaining_specs.pop(0)
        service_prices[current_spec] = price

        if remaining_specs:
            await state.update_data(remaining_specs=remaining_specs, service_prices=service_prices)
            next_spec = remaining_specs[0]
            await message.answer(f"Укажите цену за услугу «{next_spec}» (в ₽):")
        else:
            # Use average or first price as price_single for basic compatibility
            first_price = list(service_prices.values())[0] if service_prices else 0
            await state.update_data(price_single=first_price, service_prices=service_prices)
            await state.set_state(TrainerOnboarding.price_package)
            await message.answer("Шаг 7/9\n\nУкажите цену за пакет услуг (в ₽):")

    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@router.message(TrainerOnboarding.price_single)
async def process_price_single(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    try:
        price = float(message.text)
        await state.update_data(price_single=price)
        await state.set_state(TrainerOnboarding.price_package)

        user_id = effective_user_id or message.from_user.id
        async with SessionLocal() as session:
            stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
            res = await session.execute(stmt)
            profile = res.scalar_one_or_none()

            kb = None
            if profile and profile.price_package:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"Не менять ({profile.price_package}₽)", callback_data="skip_step")]
                ])
                kb = add_admin_button(kb, is_admin=is_admin)

            await message.answer("Шаг 7/9\n\nУкажите цену за абонемент на 12 занятий (в ₽):", reply_markup=kb)
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

        async with SessionLocal() as session:
            logger.info(f"Starting finish_onboarding for user {user_id}")

            # === 1. User ===
            user = await session.get(User, user_id)
            role = data.get('role', UserRole.TRAINER)
            if not user:
                user = User(
                    id=user_id,
                    username=username,
                    full_name=data.get('full_name', 'Не указано'),
                    role=role
                )
                session.add(user)
            else:
                user.role = role
                user.full_name = data.get('full_name', user.full_name)
                user.username = username or user.username

            await session.flush()

            # === 2. TrainerProfile — просто обновляем, без удаления ===
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
                    service_prices=data.get('service_prices'),
                    photo_url=photo_url,
                    video_presentation_url=video_url,
                    status="approved",
                    rating=5.0,
                    is_premium=False,
                    specializations=[]
                )
                session.add(trainer_profile)
                logger.info(f"Создан новый профиль профессионала {user_id}")
            else:
                # Обновляем существующий
                trainer_profile.city = data.get('city', trainer_profile.city)
                trainer_profile.experience = int(data.get('experience', trainer_profile.experience))
                trainer_profile.work_format = data.get('work_format', trainer_profile.work_format)
                trainer_profile.price_single = float(data.get('price_single', trainer_profile.price_single))
                trainer_profile.price_package = float(data.get('price_package', trainer_profile.price_package))
                trainer_profile.service_prices = data.get('service_prices', trainer_profile.service_prices)
                if photo_url:
                    trainer_profile.photo_url = photo_url
                if video_url:
                    trainer_profile.video_presentation_url = video_url
                trainer_profile.status = "approved"
                logger.info(f"Обновлён существующий профиль профессионала {user_id}")

            # Flush to get the trainer_profile.id if it's new, required for specializations association
            await session.flush()

            # === 3. Specializations ===
            if data.get('specializations'):
                # Robust matching for specializations during onboarding
                spec_names = [s.strip() for s in data['specializations']]
                spec_stmt = select(Specialization).where(
                    func.lower(func.trim(Specialization.name)).in_([s.lower() for s in spec_names])
                )
                spec_res = await session.execute(spec_stmt)
                found_specs = list(spec_res.scalars().all())

                # If some are missing from DB, we create them on the fly to ensure linkage
                found_names = {s.name.lower().strip() for s in found_specs}
                for name in spec_names:
                    if name.lower() not in found_names:
                        new_spec = Specialization(name=name)
                        session.add(new_spec)
                        await session.flush()
                        found_specs.append(new_spec)
                        logger.info(f"Created missing specialization: {name}")

                trainer_profile.specializations = found_specs
                logger.info(f"Linked {len(found_specs)} specializations for professional {user_id}: {[s.name for s in found_specs]}")

            await session.commit()
            logger.info(f"✅ finish_onboarding успешно завершён для {user_id}")

        await state.clear()

        role_success_text = "Ваш профиль успешно создан / обновлён."
        if data.get('role') == UserRole.BEAUTY:
            role_success_text = "Ваш профиль бьюти-мастера успешно создан / обновлён."

        await message.answer(
            f"Поздравляем! 🎉\n\n{role_success_text}",
            reply_markup=get_trainer_main_kb(is_admin=is_admin)
        )

    except Exception as e:
        logger.exception("Error in finish_onboarding")
        await message.answer("❌ Ошибка при сохранении профиля.\nПопробуйте ещё раз или напишите в поддержку.")
