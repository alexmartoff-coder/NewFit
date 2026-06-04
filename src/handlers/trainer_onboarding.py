from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from src.states.trainer_onboarding import TrainerOnboarding
from src.keyboards.common import get_format_kb
from src.models.models import User, TrainerProfile, UserRole, WorkFormat, Specialization
from src.utils.db import SessionLocal
from sqlalchemy import select

router = Router()

@router.message(F.text == "Я тренер")
async def trainer_start(message: types.Message, state: FSMContext):
    await state.set_state(TrainerOnboarding.full_name)
    await message.answer("Введите ваше ФИО:")

@router.message(TrainerOnboarding.full_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(TrainerOnboarding.city)
    await message.answer("Введите ваш город:")

@router.message(TrainerOnboarding.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(TrainerOnboarding.specialization)
    await message.answer("Введите вашу специализацию (например: похудение, кроссфит):")

@router.message(TrainerOnboarding.specialization)
async def process_specialization(message: types.Message, state: FSMContext):
    await state.update_data(specialization=message.text)
    await state.set_state(TrainerOnboarding.experience)
    await message.answer("Опишите ваш опыт работы и сертификаты:")

@router.message(TrainerOnboarding.experience)
async def process_experience(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    await state.set_state(TrainerOnboarding.formats)
    await message.answer("Выберите формат работы:", reply_markup=get_format_kb())

@router.message(TrainerOnboarding.formats)
async def process_formats(message: types.Message, state: FSMContext):
    fmt_map = {
        "Оффлайн": WorkFormat.OFFLINE,
        "Онлайн": WorkFormat.ONLINE,
        "Гибрид": WorkFormat.HYBRID
    }
    work_format = fmt_map.get(message.text)
    if not work_format:
        await message.answer("Пожалуйста, выберите формат из клавиатуры.")
        return

    await state.update_data(work_format=work_format)
    await state.set_state(TrainerOnboarding.price)
    await message.answer("Введите цену за занятие (число):")

@router.message(TrainerOnboarding.price)
async def process_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите число.")
        return

    await state.update_data(price=price)
    await state.set_state(TrainerOnboarding.media)
    await message.answer("Отправьте фото для профиля или короткое видео-презентацию (или пропустите, отправив /skip):")

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
        spec_names = [s.strip().lower() for s in data['specialization'].split(",")]
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
    await message.answer("Регистрация завершена! Ваш профиль создан.")
