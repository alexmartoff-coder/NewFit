from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.trainer_onboarding import TrainerOnboarding
from src.keyboards.common import get_format_kb, get_trainer_main_kb, get_start_reg_kb, get_spec_kb
from src.models.models import User, TrainerProfile, UserRole, WorkFormat, Specialization
from src.utils.db import SessionLocal
from sqlalchemy import select

router = Router()

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
    await callback.message.answer("Шаг 1/7\n\nНапишите ваше ФИО:")
    await callback.answer()

@router.message(TrainerOnboarding.full_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(TrainerOnboarding.city)
    await message.answer("Шаг 2/7\n\nУкажите город работы (или \"Онлайн\", если работаете только онлайн):")

@router.message(TrainerOnboarding.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(TrainerOnboarding.specialization)
    await state.update_data(specializations=[])
    await message.answer("Шаг 3/7\n\nВыберите ваши основные направления (можно несколько):", reply_markup=get_spec_kb())

@router.callback_query(F.data.startswith("spec_"), TrainerOnboarding.specialization)
async def process_spec_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "spec_done":
        data = await state.get_data()
        if not data.get('specializations'):
            await callback.answer("Выберите хотя бы одно направление!")
            return
        await state.set_state(TrainerOnboarding.experience)
        await callback.message.answer("Шаг 4/7\n\nСколько лет опыта в фитнесе?")
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
    await message.answer("Шаг 5/7\n\nКакие форматы вы предлагаете?", reply_markup=get_format_kb())

@router.callback_query(F.data.startswith("fmt_"), TrainerOnboarding.formats)
async def process_formats_callback(callback: types.CallbackQuery, state: FSMContext):
    fmt_map = {
        "fmt_offline": WorkFormat.OFFLINE,
        "fmt_online": WorkFormat.ONLINE,
        "fmt_hybrid": WorkFormat.HYBRID
    }
    work_format = fmt_map.get(callback.data)
    await state.update_data(work_format=work_format)
    await state.set_state(TrainerOnboarding.price)
    await callback.message.answer("Шаг 6/7\n\nУкажите вашу цену:\n• Разовое занятие — ____ ₽\n• Абонемент 12 занятий — ____ ₽")
    await callback.answer()

@router.message(TrainerOnboarding.price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
        return

    await state.update_data(price=price)
    await state.set_state(TrainerOnboarding.media)
    await message.answer("Шаг 7/7\n\nЗагрузите:\n1. Фото в хорошем качестве (портрет)\n2. Короткое видео-презентацию (15–60 секунд) — это очень важно для клиентов!")

@router.message(TrainerOnboarding.media)
async def process_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_url = None
    video_url = None

    if message.photo:
        photo_url = message.photo[-1].file_id
    elif message.video:
        video_url = message.video.file_id
    elif message.text == "/skip":
        pass

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

        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(
                id=message.from_user.id,
                username=message.from_user.username,
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
                price_per_session=data['price'],
                photo_url=photo_url,
                video_presentation_url=video_url,
                specializations=specializations
            )
            session.add(trainer_profile)
        else:
            trainer_profile.city = data['city']
            trainer_profile.experience = data['experience']
            trainer_profile.work_format = data['work_format']
            trainer_profile.price_per_session = data['price']
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
