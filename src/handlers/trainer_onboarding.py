import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.trainer_onboarding import TrainerOnboarding
from src.keyboards.common import get_format_kb, get_trainer_main_kb, get_start_reg_kb, get_spec_kb, get_city_kb, get_sphere_kb
from src.keyboards.inline import add_admin_button
from src.models.models import User, TrainerProfile, UserRole, WorkFormat, Specialization
from src.utils.db import SessionLocal
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

router = Router()
logger = logging.getLogger(__name__)

# --- STEP 1: Handled in start.py (Role selection) ---

# --- STEP 2: City Selection ---
@router.message(F.text == "Профи")
async def provider_role_chosen(message: types.Message, state: FSMContext):
    await state.set_state(TrainerOnboarding.city)
    await message.answer(
        "Шаг 2: Выберите ваш город или введите его:",
        reply_markup=get_city_kb()
    )

# --- STEP 3: Sphere Selection ---
@router.message(TrainerOnboarding.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await state.set_state(TrainerOnboarding.sphere)
    await message.answer(
        "Шаг 3: Выберите вашу сферу деятельности:",
        reply_markup=get_sphere_kb()
    )

# --- STEP 4: Services / Specializations ---
@router.message(TrainerOnboarding.sphere, F.text.in_(["Фитнес", "Бьюти", "Большой теннис", "Падл"]))
async def provider_sphere_chosen(message: types.Message, state: FSMContext, is_admin: bool = False):
    role_map = {
        "фитнес": UserRole.TRAINER,
        "бьюти": UserRole.BEAUTY,
        "большой теннис": UserRole.TENNIS,
        "падл": UserRole.PADEL
    }
    role = role_map.get(message.text.lower(), UserRole.TRAINER)
    await state.update_data(role=role)

    await state.set_state(TrainerOnboarding.specialization)
    kb = get_spec_kb(role=role)
    kb = add_admin_button(kb, is_admin=is_admin)

    step_texts = {
        UserRole.BEAUTY: "Шаг 4: Выберите услуги, которые вы предоставляете:",
        UserRole.TENNIS: "Шаг 4: Выберите ваши специализации в теннисе:",
        UserRole.PADEL: "Шаг 4: Выберите ваши специализации в падле:",
        UserRole.TRAINER: "Шаг 4: Выберите ваши основные направления в фитнесе:"
    }
    text = step_texts.get(role, step_texts[UserRole.TRAINER])
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("spec_"), TrainerOnboarding.specialization)
async def process_spec_callback(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    if callback.data == "spec_done":
        data = await state.get_data()
        if not data.get('specializations'):
            await callback.answer("Выберите хотя бы одно направление!")
            return

        user_id = effective_user_id or callback.from_user.id
        await state.set_state(TrainerOnboarding.full_name)

        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            kb = None
            if user and user.full_name:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"Не менять ({user.full_name})", callback_data="skip_step")]
                ])
                kb = add_admin_button(kb, is_admin=is_admin)

        await callback.message.answer("Шаг 5: Напишите ваше ФИО:", reply_markup=kb)
        await callback.answer()
        return

    # Specialization mapping logic
    spec_map = {
        "spec_strength": "Силовые тренировки",
        "spec_weight_loss": "Похудение и жиросжигание",
        "spec_func": "Функциональный тренинг",
        "spec_rehab": "Реабилитация и ОФП",
        "spec_crossfit": "Кроссфит / HIIT",
        "spec_gender": "Тренировки для женщин/мужчин",
        "spec_teens": "Работа с подростками",
        "spec_tennis": "Большой теннис",
        "spec_padl": "Падл",
        "spec_other": "Другое"
    }
    beauty_map = {
        "spec_manicure": "Маникюр", "spec_pedicure": "Педикюр", "spec_massage": "Массаж",
        "spec_cosmetology": "Косметология", "spec_hair": "Парикмахерские услуги",
        "spec_brows": "Брови и ресницы", "spec_makeup": "Макияж", "spec_other": "Другое"
    }
    tennis_map = {
        "spec_indiv": "Индивидуальные тренировки", "spec_group": "Групповые занятия",
        "spec_kids": "Тренировки для детей", "spec_tourn": "Подготовка к турнирам",
        "spec_sparr": "Спарринг", "spec_other": "Другое"
    }

    spec = spec_map.get(callback.data) or beauty_map.get(callback.data) or tennis_map.get(callback.data)
    if spec:
        data = await state.get_data()
        specs = data.get('specializations', [])
        if spec in specs:
            specs.remove(spec)
        else:
            specs.append(spec)
        await state.update_data(specializations=specs)

        kb = get_spec_kb(selected_specs=specs, role=data.get('role', 'TRAINER'))
        await callback.message.edit_reply_markup(reply_markup=add_admin_button(kb, is_admin=is_admin))

    await callback.answer()

# --- STEP 5: Full Name ---
@router.message(TrainerOnboarding.full_name)
async def process_name(message: types.Message, state: FSMContext, effective_user_id: int = None, is_admin: bool = False):
    user_id = effective_user_id or message.from_user.id
    await state.update_data(full_name=message.text, telegram_id=user_id)
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

        await message.answer("Шаг 6: Сколько лет вашего профессионального опыта?", reply_markup=kb)

# --- STEP 6: Experience ---
@router.message(TrainerOnboarding.experience)
async def process_experience(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    try:
        exp = int(message.text)
        await state.update_data(experience=exp)
        data = await state.get_data()
        role = data.get('role')

        if role in [UserRole.BEAUTY, UserRole.TENNIS, UserRole.PADEL]:
            await state.update_data(work_format=WorkFormat.OFFLINE)
            await state.set_state(TrainerOnboarding.price_services)
            specs = data.get('specializations', [])
            if specs:
                await state.update_data(remaining_specs=specs.copy(), service_prices={})
                first_spec = specs[0]
                term_price = "услугу" if role == UserRole.BEAUTY else "направление"
                await message.answer(f"Шаг 8: Укажите цену за {term_price} «{first_spec}» (в ₽):")
            else:
                await state.set_state(TrainerOnboarding.price_package)
                await message.answer("Шаг 9: Укажите цену за пакет услуг (в ₽):")
        else:
            await state.set_state(TrainerOnboarding.formats)
            kb = get_format_kb()
            await message.answer("Шаг 7: Какие форматы вы предлагаете?", reply_markup=add_admin_button(kb, is_admin=is_admin))

    except ValueError:
        await message.answer("Пожалуйста, введите число (количество полных лет опыта).")

# --- STEP 7: Formats (Fitness only) ---
@router.callback_query(F.data.startswith("fmt_"), TrainerOnboarding.formats)
async def process_formats_callback(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    fmt_map = {"fmt_offline": WorkFormat.OFFLINE, "fmt_online": WorkFormat.ONLINE, "fmt_hybrid": WorkFormat.HYBRID}
    await state.update_data(work_format=fmt_map.get(callback.data))
    await state.set_state(TrainerOnboarding.price_single)

    user_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
        stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        kb = None
        if profile and profile.price_single:
            kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=f"Не менять ({profile.price_single}₽)", callback_data="skip_step")]])
        await callback.message.answer("Шаг 8: Укажите вашу цену за разовое занятие (в ₽):", reply_markup=add_admin_button(kb, is_admin=is_admin))
    await callback.answer()

# --- STEP 8: Prices (Services/Single) ---
@router.message(TrainerOnboarding.price_services)
async def process_price_services(message: types.Message, state: FSMContext):
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
            term_price = "услугу" if data.get('role') == UserRole.BEAUTY else "направление"
            await message.answer(f"Укажите цену за {term_price} «{next_spec}» (в ₽):")
        else:
            first_price = list(service_prices.values())[0] if service_prices else 0
            await state.update_data(price_single=first_price, service_prices=service_prices)
            await state.set_state(TrainerOnboarding.price_package)
            await message.answer("Шаг 9: Укажите цену за пакет услуг (в ₽):")
    except ValueError:
        await message.answer("Введите число.")

@router.message(TrainerOnboarding.price_single)
async def process_price_single(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    try:
        await state.update_data(price_single=float(message.text))
        await state.set_state(TrainerOnboarding.price_package)
        user_id = effective_user_id or message.from_user.id
        async with SessionLocal() as session:
            profile = (await session.execute(select(TrainerProfile).where(TrainerProfile.user_id == user_id))).scalar_one_or_none()
            kb = None
            if profile and profile.price_package:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=f"Не менять ({profile.price_package}₽)", callback_data="skip_step")]])
            await message.answer("Шаг 9: Укажите цену за пакет услуг (в ₽):", reply_markup=add_admin_button(kb, is_admin=is_admin))
    except ValueError:
        await message.answer("Введите число.")

# --- STEP 9: Price Package ---
@router.message(TrainerOnboarding.price_package)
async def process_price_package(message: types.Message, state: FSMContext):
    try:
        await state.update_data(price_package=float(message.text))
        await state.set_state(TrainerOnboarding.photo)
        await message.answer("Загрузите ваше фото в хорошем качестве (портрет):", reply_markup=types.ReplyKeyboardRemove())
    except ValueError:
        await message.answer("Введите число.")

# --- PHOTO & VIDEO ---
@router.message(TrainerOnboarding.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext, is_admin: bool = False):
    await state.update_data(photo_url=message.photo[-1].file_id)
    await state.set_state(TrainerOnboarding.video)
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Пропустить", callback_data="skip_video")]])
    await message.answer("Загрузите короткое видео-презентацию (15–60 секунд) или пропустите этот шаг.", reply_markup=add_admin_button(kb, is_admin=is_admin))

@router.callback_query(F.data == "skip_video", TrainerOnboarding.video)
async def skip_video(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    await callback.message.edit_reply_markup(reply_markup=None)
    await finish_onboarding(callback.message, state, effective_user_id or callback.from_user.id, callback.from_user.username, is_admin)

@router.message(TrainerOnboarding.video, F.video)
async def process_video(message: types.Message, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    await state.update_data(video_url=message.video.file_id)
    await finish_onboarding(message, state, effective_user_id or message.from_user.id, message.from_user.username, is_admin)

# --- SKIP STEP HANDLER ---
@router.callback_query(F.data == "skip_step")
async def skip_step_handler(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False, effective_user_id: int = None):
    current_state = await state.get_state()
    user_id = effective_user_id or callback.from_user.id
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        profile = (await session.execute(select(TrainerProfile).where(TrainerProfile.user_id == user_id).options(selectinload(TrainerProfile.specializations)))).scalar_one_or_none()

        if current_state == TrainerOnboarding.full_name:
            await state.update_data(full_name=user.full_name)
            await state.set_state(TrainerOnboarding.experience)
            kb = None
            if profile and profile.experience:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=f"Не менять ({profile.experience} лет)", callback_data="skip_step")]])
            await callback.message.answer("Шаг 6: Сколько лет вашего профессионального опыта?", reply_markup=add_admin_button(kb, is_admin=is_admin))

        elif current_state == TrainerOnboarding.experience:
            await process_experience(types.Message(text=str(profile.experience), from_user=callback.from_user, chat=callback.message.chat, date=callback.message.date), state, is_admin, user_id)

        elif current_state == TrainerOnboarding.price_single:
            await state.update_data(price_single=profile.price_single)
            await state.set_state(TrainerOnboarding.price_package)
            kb = None
            if profile and profile.price_package:
                kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=f"Не менять ({profile.price_package}₽)", callback_data="skip_step")]])
            await callback.message.answer("Шаг 9: Укажите цену за пакет услуг (в ₽):", reply_markup=add_admin_button(kb, is_admin=is_admin))

        elif current_state == TrainerOnboarding.price_package:
            await state.update_data(price_package=profile.price_package)
            await state.set_state(TrainerOnboarding.photo)
            await callback.message.answer("Загрузите ваше фото или оставьте прежнее:", reply_markup=types.ReplyKeyboardRemove())

        elif current_state == TrainerOnboarding.photo:
            await state.update_data(photo_url=profile.photo_url)
            await state.set_state(TrainerOnboarding.video)
            kb = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="Пропустить", callback_data="skip_video")], [types.InlineKeyboardButton(text="Не менять видео", callback_data="skip_step")]])
            await callback.message.answer("Загрузите видео-презентацию:", reply_markup=add_admin_button(kb, is_admin=is_admin))
    await callback.answer()

# --- FINISH ---
async def finish_onboarding(message: types.Message, state: FSMContext, user_id: int, username: str, is_admin: bool = False):
    try:
        data = await state.get_data()
        user_id = data.get('telegram_id', user_id)
        async with SessionLocal() as session:
            user = await session.get(User, user_id)
            role = data.get('role', UserRole.TRAINER)
            if not user:
                user = User(id=user_id, username=username, full_name=data.get('full_name', 'Не указано'), role=role)
                session.add(user)
            else:
                user.role = role
                user.full_name = data.get('full_name', user.full_name)
            await session.flush()

            profile = (await session.execute(select(TrainerProfile).where(TrainerProfile.user_id == user_id).options(selectinload(TrainerProfile.specializations)))).scalar_one_or_none()
            if not profile:
                profile = TrainerProfile(user_id=user_id, city=data.get('city', 'Не указан'), experience=int(data.get('experience', 0)), work_format=data.get('work_format', WorkFormat.ONLINE), price_single=float(data.get('price_single', 0)), price_package=float(data.get('price_package', 0)), service_prices=data.get('service_prices'), photo_url=data.get('photo_url'), video_presentation_url=data.get('video_url'), status="approved")
                session.add(profile)
            else:
                profile.city = data.get('city', profile.city)
                profile.experience = int(data.get('experience', profile.experience))
                profile.work_format = data.get('work_format', profile.work_format)
                profile.price_single = float(data.get('price_single', profile.price_single))
                profile.price_package = float(data.get('price_package', profile.price_package))
                profile.service_prices = data.get('service_prices', profile.service_prices)
                if data.get('photo_url'): profile.photo_url = data.get('photo_url')
                if data.get('video_url'): profile.video_presentation_url = data.get('video_url')

            await session.flush()
            if data.get('specializations'):
                spec_names = [s.strip() for s in data['specializations']]
                found_specs = list((await session.execute(select(Specialization).where(func.lower(func.trim(Specialization.name)).in_([s.lower() for s in spec_names])))).scalars().all())
                profile.specializations.clear()
                for s in found_specs: profile.specializations.append(s)
            await session.commit()
        await state.clear()
        await message.answer(f"Поздравляем! 🎉 Профиль успешно {'обновлён' if profile else 'создан'}.", reply_markup=get_trainer_main_kb(is_admin=is_admin))
    except Exception as e:
        logger.exception("Error in finish_onboarding")
        await message.answer("❌ Ошибка при сохранении профиля.")
