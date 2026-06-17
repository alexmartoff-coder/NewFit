from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_, func
from src.models.models import TrainerProfile, User, Specialization
from src.utils.db import SessionLocal
from src.keyboards.catalog import get_filter_kb, get_price_filter_kb
from src.keyboards.inline import add_admin_button
from src.states.catalog import CatalogFilter

router = Router()

@router.message(F.text == "Выбрать услугу")
@router.message(F.text == "/search")
async def start_catalog(message: types.Message, state: FSMContext):
    await state.clear()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Фитнес", callback_data="cat_type_fitness")],
        [types.InlineKeyboardButton(text="Бьюти", callback_data="cat_type_beauty")]
    ])
    await message.answer("Какая сфера услуг вас интересует?", reply_markup=kb)

@router.callback_query(F.data.startswith("cat_type_"))
async def process_catalog_type(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    cat_type = callback.data.split("_")[2]
    await state.update_data(catalog_type=cat_type)

    # Directly show specializations (services) buttons
    from src.keyboards.common import get_spec_kb
    role = "TRAINER" if cat_type == "fitness" else "BEAUTY"
    kb = get_spec_kb(role=role)
    kb = add_admin_button(kb, is_admin=is_admin)

    text = "Выберите услугу:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(CatalogFilter.entering_specialization)
    await callback.answer()

@router.callback_query(F.data == "filter_city")
async def filter_city(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.entering_city)
    await callback.message.answer("Введите название города:")
    await callback.answer()

@router.message(CatalogFilter.entering_city)
async def process_filter_city(message: types.Message, state: FSMContext, is_admin: bool = False):
    await state.update_data(city=message.text)
    kb = get_filter_kb()
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer(
        f"Город установлен: {message.text}\n"
        "Выберите дополнительные фильтры или нажмите 'Показать':",
        reply_markup=kb
    )

@router.callback_query(F.data == "filter_spec")
async def filter_spec(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    await state.set_state(CatalogFilter.entering_specialization)
    data = await state.get_data()
    selected = data.get("specializations", [])
    from src.keyboards.common import get_spec_kb
    kb = get_spec_kb(selected_specs=selected)
    kb = add_admin_button(kb, is_admin=is_admin)

    text = "Выберите направления (можно несколько):"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("spec_"), CatalogFilter.entering_specialization)
async def process_filter_spec_callback(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    if callback.data == "spec_done":
        kb = get_filter_kb()
        kb = add_admin_button(kb, is_admin=is_admin)
        text = "Фильтры настроены:"
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=kb)
        else:
            await callback.message.edit_text(text, reply_markup=kb)
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
        else:
            specs.append(spec)
        await state.update_data(specializations=specs)

        from src.keyboards.common import get_spec_kb
        role = "TRAINER" if data.get('catalog_type') == "fitness" else "BEAUTY"
        kb = get_spec_kb(selected_specs=specs, role=role)
        kb = add_admin_button(kb, is_admin=is_admin)
        await callback.message.edit_reply_markup(reply_markup=kb)

    await callback.answer()

@router.callback_query(F.data == "filter_price")
async def filter_price(callback: types.CallbackQuery, is_admin: bool = False):
    kb = get_price_filter_kb()
    kb = add_admin_button(kb, is_admin=is_admin)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "filter_back")
async def filter_back(callback: types.CallbackQuery, is_admin: bool = False):
    kb = get_filter_kb()
    kb = add_admin_button(kb, is_admin=is_admin)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "price_min")
async def filter_price_min(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.entering_price_min)
    await callback.message.answer("Введите минимальную цену:")
    await callback.answer()

@router.message(CatalogFilter.entering_price_min)
async def process_price_min(message: types.Message, state: FSMContext, is_admin: bool = False):
    try:
        val = float(message.text)
        await state.update_data(price_min=val)
        kb = get_filter_kb()
        kb = add_admin_button(kb, is_admin=is_admin)
        await message.answer(f"Мин. цена: {val}", reply_markup=kb)
    except ValueError:
        await message.answer("Введите число.")

@router.callback_query(F.data == "price_max")
async def filter_price_max(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.entering_price_max)
    await callback.message.answer("Введите максимальную цену:")
    await callback.answer()

@router.message(CatalogFilter.entering_price_max)
async def process_price_max(message: types.Message, state: FSMContext, is_admin: bool = False):
    try:
        val = float(message.text)
        await state.update_data(price_max=val)
        kb = get_filter_kb()
        kb = add_admin_button(kb, is_admin=is_admin)
        await message.answer(f"Макс. цена: {val}", reply_markup=kb)
    except ValueError:
        await message.answer("Введите число.")

@router.callback_query(F.data == "filter_reset")
async def filter_reset(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    await state.clear()
    kb = get_filter_kb()
    kb = add_admin_button(kb, is_admin=is_admin)
    text = "Фильтры сброшены. Выберите снова:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "filter_apply")
@router.callback_query(F.data.startswith("cat_page_"))
async def apply_filters(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    page = 0
    if callback.data.startswith("cat_page_"):
        page = int(callback.data.split("_")[2])

    limit = 5
    offset = page * limit

    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        query = select(TrainerProfile, User).join(User, TrainerProfile.user_id == User.id).options(selectinload(TrainerProfile.specializations))

        filters = [TrainerProfile.status == "approved"]
        if 'city' in data:
            filters.append(func.lower(TrainerProfile.city) == func.lower(data['city']))
        if 'price_min' in data:
            filters.append(TrainerProfile.price_single >= data['price_min'])
        if 'price_max' in data:
            filters.append(TrainerProfile.price_single <= data['price_max'])

        if filters:
            query = query.where(and_(*filters))

        if 'specializations' in data and data['specializations']:
            # Filtering by multiple specializations
            spec_names = [s for s in data['specializations']]
            spec_query = select(Specialization.id).where(Specialization.name.in_(spec_names))
            spec_res = await session.execute(spec_query)
            spec_ids = list(spec_res.scalars().all())

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Filtering by specializations: {spec_names}, IDs found: {spec_ids}")

            if spec_ids:
                # Trainer must have AT LEAST ONE of the selected specializations
                query = query.where(TrainerProfile.specializations.any(Specialization.id.in_(spec_ids)))
            else:
                await callback.message.answer("Мастера с выбранными специализациями не найдены.")
                await callback.answer()
                return

        # Total count for pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_res = await session.execute(count_query)
        total_count = total_res.scalar_one()

        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        professionals = result.all()

        if not professionals:
            await callback.message.answer("К сожалению, профессионалов по вашему запросу не найдено.")
        else:
            for trainer_profile, user in professionals:
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
                        [types.InlineKeyboardButton(text="📅 Записаться", callback_data=f"book_{trainer_profile.user_id}")],
                        [types.InlineKeyboardButton(text="🔙 Назад к фильтрам", callback_data="filter_back")]
                    ]
                )
                if trainer_profile.photo_url:
                    await callback.message.answer_photo(trainer_profile.photo_url, caption=text, reply_markup=kb)
                else:
                    await callback.message.answer(text, reply_markup=kb)

            # Pagination buttons
            pagination_buttons = []
            if page > 0:
                pagination_buttons.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_page_{page-1}"))
            if offset + limit < total_count:
                pagination_buttons.append(types.InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"cat_page_{page+1}"))

            if pagination_buttons:
                await callback.message.answer(
                    f"Страница {page+1} из {(total_count + limit - 1) // limit}",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[pagination_buttons])
                )

    await callback.answer()
