import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.trainer_onboarding import TrainerOnboarding
from src.keyboards.common import get_format_kb, get_trainer_main_kb, get_start_reg_kb, get_spec_kb, get_city_kb
from src.models.models import User, TrainerProfile, UserRole, WorkFormat, Specialization
from src.utils.db import SessionLocal
from sqlalchemy import select

router = Router()
logger = logging.getLogger(__name__)

@router.message(F.text == "👨‍🏫 Я тренер")
async def trainer_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Отлично! Давайте создадим ваш профессиональный профиль в NewFit.\n\n"
        "Это займёт около 3-4 минут.\n\n"
        "Готовы начать?",
        reply_markup=get_start_reg_kb()
    )

@router.callback_query(F.data == "start_registration")
async def start_reg(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TrainerOnboarding.full_name)
    await callback.message.answer("Шаг 1/9\n\nНапишите ваше ФИО:")
    await callback.answer()

@router.message(TrainerOnboarding.full_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(TrainerOnboarding.city)
    await message.answer(
        "Шаг 2/9\n\nУкажите город работы (или \"Онлайн\", если работаете только онлайн):",
        reply_markup=get_city_kb()
    )

@router.message(TrainerOnboarding.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(TrainerOnboarding.specialization)
    await state.update_data(specializations=[])
    await message.answer("Шаг 3/9\n\nВыберите ваши основные направления (можно несколько):", reply_markup=get_spec_kb())

@router.callback_query(F.data.startswith("spec_"), TrainerOnboarding.specialization)
async def process_spec_callback(callback: types.CallbackQuery, state: FSMContext):
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

    await callback.answer()

@router.message(TrainerOnboarding.experience)
async def process_experience(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(TrainerOnboarding.formats)
    await message.answer("Шаг 5/9\n\nКакие форматы вы предлагаете?", reply_markup=get_format_kb())

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
        await message.answer("Шаг 8/9\n\nЗагрузите ваше фото в хорошем качестве (портрет):")
    except ValueError:
        await message.answer("Пожалуйста, введите число.")

@router.message(TrainerOnboarding.photo, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_url=photo_id)
    await state.set_state(TrainerOnboarding.video)
    await message.answer(
        "Шаг 9/9\n\nЗагрузите короткое видео-презентацию (15–60 секунд).\n"
        "Это очень важно для клиентов! Вы также можете пропустить этот шаг.",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="Пропустить", callback_data="skip_video")]]
        )
    )

@router.callback_query(F.data == "skip_video", TrainerOnboarding.video)
async def skip_video(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Видео пропущено.")
    # Remove reply markup to avoid double clicking
    await callback.message.edit_reply_markup(reply_markup=None)
    await finish_onboarding(callback.message, state, callback.from_user.id, callback.from_user.username)

@router.message(TrainerOnboarding.video, F.video)
async def process_video(message: types.Message, state: FSMContext):
    video_id = message.video.file_id
    await state.update_data(video_url=video_id)
    await finish_onboarding(message, state, message.from_user.id, message.from_user.username)

async def finish_onboarding(message: types.Message, state: FSMContext, user_id: int, username: str):
    try:
        data = await state.get_data()
        photo_url = data.get('photo_url')
        video_url = data.get('video_url')

        async with SessionLocal() as session:
            # Specializations handling
            spec_names = [s.lower() for s in data.get('specializations', [])]
            specializations = []
            for name in spec_names:
                stmt = select(Specialization).where(Specialization.name == name)
                res = await session.execute(stmt)
                spec = res.scalar_one_or_none()
                if not spec:
                    spec = Specialization(name=name)
                    session.add(spec)
                    await session.flush()
                specializations.append(spec)

            user = await session.get(User, user_id)
            if not user:
                user = User(
                    id=user_id,
                    username=username,
                    full_name=data['full_name'],
                    role=UserRole.TRAINER
                )
                session.add(user)
            else:
                user.role = UserRole.TRAINER
                user.full_name = data['full_name']

            # Check if profile already exists
            stmt = select(TrainerProfile).where(TrainerProfile.user_id == user.id)
            res = await session.execute(stmt)
            trainer_profile = res.scalar_one_or_none()

            if not trainer_profile:
                trainer_profile = TrainerProfile(
                    user_id=user.id,
                    city=data['city'],
                    experience=data['experience'],
                    work_format=data['work_format'],
                    price_single=data.get('price_single', 0.0),
                    price_package=data.get('price_package', 0.0),
                    photo_url=photo_url,
                    video_presentation_url=video_url,
                    specializations=specializations
                )
                session.add(trainer_profile)
            else:
                trainer_profile.city = data['city']
                trainer_profile.experience = data['experience']
                trainer_profile.work_format = data['work_format']
                trainer_profile.price_single = data.get('price_single', trainer_profile.price_single)
                trainer_profile.price_package = data.get('price_package', trainer_profile.price_package)
                trainer_profile.photo_url = photo_url or trainer_profile.photo_url
                trainer_profile.video_presentation_url = video_url or trainer_profile.video_presentation_url
                trainer_profile.specializations = specializations

            await session.commit()

        await state.clear()
        await message.answer(
            "Поздравляем! 🎉\n\n"
            "Ваш профиль создан и отправлен на модерацию.\n\n"
            "В течение 24 часов администрация NewFit поможет вам красиво оформить аккаунт, снять презентационные рилсы и запустить первые продажи.\n\n"
            "Вы уже можете пользоваться кабинетом тренера.",
            reply_markup=get_trainer_main_kb()
        )
    except Exception as e:
        logger.exception("Error in finish_onboarding")
        await message.answer(f"Произошла ошибка при сохранении профиля. Пожалуйста, попробуйте позже или обратитесь в поддержку.")
