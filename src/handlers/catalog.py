from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_
from src.models.models import TrainerProfile, User, Specialization
from src.utils.db import SessionLocal
from src.keyboards.catalog import get_filter_kb, get_price_filter_kb
from src.states.catalog import CatalogFilter

router = Router()

@router.message(F.text == "🔍 Найти тренера")
@router.message(F.text == "/search")
async def start_catalog(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Выберите фильтры для поиска тренера или нажмите 'Показать':",
        reply_markup=get_filter_kb()
    )

@router.callback_query(F.data == "filter_city")
async def filter_city(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.entering_city)
    await callback.message.answer("Введите название города:")
    await callback.answer()

@router.message(CatalogFilter.entering_city)
async def process_filter_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer(f"Город установлен: {message.text}", reply_markup=get_filter_kb())

@router.callback_query(F.data == "filter_spec")
async def filter_spec(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.entering_specialization)
    await callback.message.answer("Введите специализацию:")
    await callback.answer()

@router.message(CatalogFilter.entering_specialization)
async def process_filter_spec(message: types.Message, state: FSMContext):
    await state.update_data(specialization=message.text)
    await message.answer(f"Специализация установлена: {message.text}", reply_markup=get_filter_kb())

@router.callback_query(F.data == "filter_price")
async def filter_price(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=get_price_filter_kb())
    await callback.answer()

@router.callback_query(F.data == "filter_back")
async def filter_back(callback: types.CallbackQuery):
    await callback.message.edit_reply_markup(reply_markup=get_filter_kb())
    await callback.answer()

@router.callback_query(F.data == "price_min")
async def filter_price_min(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.entering_price_min)
    await callback.message.answer("Введите минимальную цену:")
    await callback.answer()

@router.message(CatalogFilter.entering_price_min)
async def process_price_min(message: types.Message, state: FSMContext):
    try:
        val = float(message.text)
        await state.update_data(price_min=val)
        await message.answer(f"Мин. цена: {val}", reply_markup=get_filter_kb())
    except ValueError:
        await message.answer("Введите число.")

@router.callback_query(F.data == "filter_reset")
async def filter_reset(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Фильтры сброшены. Выберите снова:", reply_markup=get_filter_kb())
    await callback.answer()

@router.callback_query(F.data == "filter_apply")
async def apply_filters(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with SessionLocal() as session:
        query = select(TrainerProfile, User).join(User, TrainerProfile.user_id == User.id)

        filters = []
        if 'city' in data:
            filters.append(TrainerProfile.city.ilike(f"%{data['city']}%"))
        if 'price_min' in data:
            filters.append(TrainerProfile.price_single >= data['price_min'])
        if 'price_max' in data:
            filters.append(TrainerProfile.price_single <= data['price_max'])

        if filters:
            query = query.where(and_(*filters))

        if 'specialization' in data:
            # Filtering by specialization is more complex due to many-to-many
            spec_query = select(Specialization.id).where(Specialization.name.ilike(f"%{data['specialization']}%"))
            spec_res = await session.execute(spec_query)
            spec_ids = spec_res.scalars().all()
            if spec_ids:
                query = query.where(TrainerProfile.specializations.any(Specialization.id.in_(spec_ids)))
            else:
                # No such specialization found
                await callback.message.answer("Тренеры с такой специализацией не найдены.")
                await callback.answer()
                return

        result = await session.execute(query)
        trainers = result.all()

        if not trainers:
            await callback.message.answer("К сожалению, тренеров по вашему запросу не найдено.")
        else:
            for trainer_profile, user in trainers:
                text = (
                    f"👤 {user.full_name}\n"
                    f"📍 Город: {trainer_profile.city}\n"
                    f"💪 Опыт: {trainer_profile.experience}\n"
                    f"💰 Разовое: {trainer_profile.price_single}₽\n"
                    f"💳 12 занятий: {trainer_profile.price_package}₽\n"
                    f"⭐ Рейтинг: {trainer_profile.rating}\n"
                    f"📝 Формат: {trainer_profile.work_format.value}"
                )
                kb = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(text="📅 Записаться", callback_data=f"book_{trainer_profile.id}")]
                    ]
                )
                if trainer_profile.photo_url:
                    await callback.message.answer_photo(trainer_profile.photo_url, caption=text, reply_markup=kb)
                else:
                    await callback.message.answer(text, reply_markup=kb)

    await callback.answer()
