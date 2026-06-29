from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, and_, func
from src.models.models import TrainerProfile, User, Specialization, UserRole
from src.utils.db import SessionLocal
from src.keyboards.catalog import get_filter_kb, get_price_filter_kb
from src.keyboards.inline import add_admin_button
from src.keyboards.common import get_district_kb
from src.states.catalog import CatalogFilter

router = Router()

@router.message(F.text == "Выбрать услугу")
@router.message(F.text == "/search")
async def start_catalog(message: types.Message, state: FSMContext):
    await state.clear()
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📍 Поиск по городу/району", callback_data="filter_city")],
        [types.InlineKeyboardButton(text="📞 Поиск по номеру телефона", callback_data="search_by_phone")],
        [types.InlineKeyboardButton(text="🔍 Поиск по Nickname ТГ", callback_data="search_by_username")],
        [types.InlineKeyboardButton(text="👤 Поиск по ФИО", callback_data="search_by_name")],
        [types.InlineKeyboardButton(text="🏠 В главное меню", callback_data="client_menu")]
    ])
    await message.answer("Как вы хотите найти мастера?", reply_markup=kb)

@router.callback_query(F.data == "search_by_username")
async def search_by_username_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.waiting_for_username_search)
    await callback.message.edit_text("Введите Telegram Nickname (username) мастера для поиска (с @ или без):")
    await callback.answer()

@router.message(F.text, CatalogFilter.waiting_for_username_search)
async def process_username_search(message: types.Message, state: FSMContext):
    username = message.text.strip().replace("@", "")
    if len(username) < 3:
        await message.answer("Пожалуйста, введите корректный Nickname (минимум 3 символа).")
        return

    await state.clear()
    await state.update_data(username_search=username)

    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        stmt = select(TrainerProfile, User).join(User).where(
            func.lower(User.username).like(f"%{username.lower()}%")
        ).options(selectinload(TrainerProfile.specializations))
        res = await session.execute(stmt)
        professionals = res.all()

        if not professionals:
            await message.answer(f"Мастер с Nickname '{username}' не найден.")
            return

        await message.answer(f"Найдено мастеров: {len(professionals)}")
        await apply_filters(message, state)

@router.callback_query(F.data == "search_by_phone")
async def search_by_phone_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.waiting_for_phone_search)
    await callback.message.edit_text("Введите номер телефона мастера для поиска:")
    await callback.answer()

@router.callback_query(F.data == "search_by_name")
async def search_by_name_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.waiting_for_name_search)
    await callback.message.edit_text("Введите ФИО (или часть имени) мастера для поиска:")
    await callback.answer()

@router.message(F.text, CatalogFilter.waiting_for_name_search)
async def process_name_search(message: types.Message, state: FSMContext):
    name_query = message.text.strip()
    if len(name_query) < 2:
        await message.answer("Пожалуйста, введите минимум 2 символа для поиска.")
        return

    await state.clear()
    await state.update_data(name_search=name_query)

    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        stmt = select(TrainerProfile, User).join(User).where(
            User.full_name.ilike(f"%{name_query}%")
        ).options(selectinload(TrainerProfile.specializations))
        res = await session.execute(stmt)
        professionals = res.all()

        if not professionals:
            await message.answer(f"Мастер с именем '{name_query}' не найден.")
            return

        await message.answer(f"Найдено мастеров: {len(professionals)}")
        await apply_filters(message, state)

@router.message(F.text, CatalogFilter.waiting_for_phone_search)
async def process_phone_search(message: types.Message, state: FSMContext):
    raw_phone = "".join(filter(str.isdigit, message.text))
    if not raw_phone or len(raw_phone) < 3:
        await message.answer("Пожалуйста, введите корректный номер телефона (минимум 3 цифры).")
        return

    # Normalize: if starts with 7 or 8 and is long, treat as interchangeable
    search_phone = raw_phone
    if len(raw_phone) >= 10:
        if raw_phone.startswith('7') or raw_phone.startswith('8'):
            search_phone = raw_phone[1:]

    # Clear state to make phone search global (ignore previous city/spec filters)
    await state.clear()
    await state.update_data(phone_search=search_phone)

    # Basic phone normalization or search
    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        # Use regexp_replace on DB side for even more robust search
        # We search for the suffix to handle 7/8 interchangeable starts
        stmt = select(TrainerProfile, User).join(User).where(
            func.regexp_replace(TrainerProfile.phone, '\D', '', 'g').like(f"%{search_phone}%")
        ).options(selectinload(TrainerProfile.specializations))
        res = await session.execute(stmt)
        professionals = res.all()

        if not professionals:
            await message.answer("Мастер с таким номером не найден.")
            return

        await message.answer(f"Найдено мастеров: {len(professionals)}")
        await apply_filters(message, state)

@router.callback_query(F.data.startswith("cat_city_"))
async def process_catalog_city(callback: types.CallbackQuery, state: FSMContext):
    city = callback.data.split("_")[2]
    await state.update_data(city=city)

    if city == "Онлайн":
        await state.update_data(district=None)
        # Proceed to sphere
    else:
        dist_kb = get_district_kb(city)
        if dist_kb:
            await state.set_state(CatalogFilter.entering_district)
            await callback.message.answer(f"Выберите район в г. {city}:", reply_markup=dist_kb)
            await callback.answer()
            return

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Фитнес", callback_data="cat_type_fitness")],
        [types.InlineKeyboardButton(text="Бьюти", callback_data="cat_type_beauty")],
        [types.InlineKeyboardButton(text="Большой теннис", callback_data="cat_type_tennis")],
        [types.InlineKeyboardButton(text="Падл", callback_data="cat_type_padel")]
    ])
    text = f"Город: {city}\n\nКакая сфера услуг вас интересует?"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("cat_type_"))
async def process_catalog_type(callback: types.CallbackQuery, state: FSMContext, is_admin: bool = False):
    cat_type = callback.data.split("_")[2]
    await state.update_data(catalog_type=cat_type)

    # Directly show specializations (services) buttons
    from src.keyboards.common import get_spec_kb
    data = await state.get_data()
    role_map = {
        "fitness": "TRAINER",
        "beauty": "BEAUTY",
        "tennis": "TENNIS",
        "padel": "PADEL"
    }
    role = role_map.get(cat_type, "TRAINER")
    kb = get_spec_kb(role=role)
    kb = add_admin_button(kb, is_admin=is_admin)

    type_names = {"fitness": "Фитнес", "beauty": "Бьюти", "tennis": "Большой теннис", "padel": "Падл"}
    text = f"Город: {data.get('city')}\nСфера: {type_names.get(cat_type, cat_type)}\n\nВыберите услугу:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(CatalogFilter.entering_specialization)
    await callback.answer()

@router.callback_query(F.data == "filter_city")
async def filter_city(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CatalogFilter.entering_city)
    from src.keyboards.common import get_city_kb
    await callback.message.answer("Выберите или введите название города:", reply_markup=get_city_kb())
    await callback.answer()

@router.message(CatalogFilter.entering_city)
async def process_filter_city(message: types.Message, state: FSMContext, is_admin: bool = False):
    city = message.text.strip()
    await state.update_data(city=city)

    if city == "Онлайн":
        kb = get_filter_kb()
        kb = add_admin_button(kb, is_admin=is_admin)
        await message.answer(
            f"Город установлен: {city}\n"
            "Выберите дополнительные фильтры или нажмите 'Показать':",
            reply_markup=kb
        )
    else:
        dist_kb = get_district_kb(city)
        if dist_kb:
            await state.set_state(CatalogFilter.entering_district)
            await message.answer(f"Выберите район в г. {city}:", reply_markup=dist_kb)
        else:
            kb = get_filter_kb()
            kb = add_admin_button(kb, is_admin=is_admin)
            await message.answer(
                f"Город установлен: {city}\n"
                "Выберите дополнительные фильтры или нажмите 'Показать':",
                reply_markup=kb
            )

@router.message(CatalogFilter.entering_district)
async def process_filter_district(message: types.Message, state: FSMContext, is_admin: bool = False):
    district = message.text.strip()
    await state.update_data(district=district)
    kb = get_filter_kb()
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer(
        f"Район установлен: {district}\n"
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
        # Skip the "Filters configured" menu and show results immediately
        await apply_filters(callback, state)
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

    tennis_map = {
        "spec_indiv": "Индивидуальные тренировки",
        "spec_group": "Групповые занятия",
        "spec_kids": "Тренировки для детей",
        "spec_tourn": "Подготовка к турнирам",
        "spec_sparr": "Спарринг",
        "spec_other": "Другое"
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

        from src.keyboards.common import get_spec_kb
        cat_type = data.get('catalog_type')
        role_map = {
            "fitness": "TRAINER",
            "beauty": "BEAUTY",
            "tennis": "TENNIS",
            "padel": "PADEL"
        }
        role = role_map.get(cat_type, "TRAINER")
        kb = get_spec_kb(selected_specs=specs, role=role)
        kb = add_admin_button(kb, is_admin=is_admin)
        await callback.message.edit_reply_markup(reply_markup=kb)

    if callback:
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
async def apply_filters(event: types.CallbackQuery | types.Message, state: FSMContext):
    if isinstance(event, types.CallbackQuery):
        callback = event
        message = event.message
    else:
        callback = None
        message = event

    data = await state.get_data()
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Applying filters: {data}")

    page = 0
    if callback and callback.data.startswith("cat_page_"):
        page = int(callback.data.split("_")[2])

    limit = 5
    offset = page * limit

    async with SessionLocal() as session:
        from sqlalchemy.orm import selectinload
        query = select(TrainerProfile, User).join(User, TrainerProfile.user_id == User.id).options(selectinload(TrainerProfile.specializations))

        filters = [TrainerProfile.status == "approved"]

        if 'phone_search' in data:
            filters.append(func.regexp_replace(TrainerProfile.phone, '\D', '', 'g').like(f"%{data['phone_search']}%"))
        elif 'username_search' in data:
            filters.append(func.lower(User.username).like(f"%{data['username_search'].lower()}%"))
        elif 'name_search' in data:
            filters.append(User.full_name.ilike(f"%{data['name_search']}%"))
        else:
            # Filter by role based on catalog type (only if not searching by phone)
            cat_type = data.get('catalog_type')
            role_filter_map = {
                "fitness": UserRole.TRAINER,
                "beauty": UserRole.BEAUTY,
                "tennis": UserRole.TENNIS,
                "padel": UserRole.PADEL
            }
            if cat_type in role_filter_map:
                filters.append(User.role == role_filter_map[cat_type])
        if 'city' in data:
            filters.append(func.lower(TrainerProfile.city) == func.lower(data['city'].strip()))
        if 'district' in data and data['district']:
            filters.append(func.lower(TrainerProfile.district) == func.lower(data['district'].strip()))
        if 'price_min' in data:
            filters.append(TrainerProfile.price_single >= data['price_min'])
        if 'price_max' in data:
            filters.append(TrainerProfile.price_single <= data['price_max'])

        if filters:
            query = query.where(and_(*filters))

        if 'specializations' in data and data['specializations']:
            # Filtering by multiple specializations
            spec_names = [s.strip() for s in data['specializations']]

            # Robust matching using lower() and trim() on DB side
            spec_query = select(Specialization.id).where(
                func.lower(func.trim(Specialization.name)).in_([s.lower() for s in spec_names])
            )
            spec_res = await session.execute(spec_query)
            spec_ids = list(spec_res.scalars().all())

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Filtering by specializations: {spec_names}, IDs found: {spec_ids}")

            if spec_ids:
                from src.models.models import trainer_specializations
                # Use subquery to avoid DISTINCT on JSON columns which causes errors in Postgres
                spec_subquery = select(trainer_specializations.c.trainer_id).where(
                    trainer_specializations.c.specialization_id.in_(spec_ids)
                )
                query = query.where(TrainerProfile.id.in_(spec_subquery))
            else:
                # Log available specializations if filtering failed
                all_specs_res = await session.execute(select(Specialization.name))
                all_specs = all_specs_res.scalars().all()
                logger.warning(f"Filter ID mismatch. Available specializations in DB: {all_specs}")
                await message.answer("Мастера с выбранными специализациями не найдены.")
                if callback:
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
            kb = get_filter_kb()
            text = "❌ К сожалению, профессионалов по вашему запросу не найдено.\n\nПопробуйте изменить город или сбросить фильтры."
            if callback:
                if message.photo:
                    await message.edit_caption(caption=text, reply_markup=kb)
                else:
                    await message.edit_text(text, reply_markup=kb)
            else:
                await message.answer(text, reply_markup=kb)
        else:
            fmt_map = {"OFFLINE": "оффлайн", "ONLINE": "онлайн", "HYBRID": "гибрид"}
            for trainer_profile, user in professionals:
                # Capture current specializations for this profile to pass to booking state
                current_profile_specs = [s.name for s in trainer_profile.specializations]
                specs_str = ", ".join(current_profile_specs) or "не указаны"
                work_fmt = trainer_profile.work_format.value if hasattr(trainer_profile.work_format, 'value') else str(trainer_profile.work_format)
                work_fmt_ru = fmt_map.get(work_fmt, work_fmt.lower())

                dist_text = f"\n🏙 Район: {trainer_profile.district}" if trainer_profile.district else ""
                phone_text = f"\n📞 Телефон: {trainer_profile.phone}" if trainer_profile.phone else ""

                text = (
                    f"👤 **{user.full_name}**\n"
                    f"📍 Город: {trainer_profile.city}{dist_text}{phone_text}\n"
                    f"💪 Опыт: {trainer_profile.experience} лет\n"
                    f"🎯 Специализации: {specs_str}\n"
                    f"💰 Разовое: {trainer_profile.price_single}₽\n"
                    f"💳 12 занятий: {trainer_profile.price_package}₽\n"
                    f"⭐ Рейтинг: {trainer_profile.rating:.1f}\n"
                    f"📝 Формат: {work_fmt_ru}"
                )
                kb = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(text="📅 Записаться", callback_data=f"book_{trainer_profile.user_id}")],
                        [types.InlineKeyboardButton(text="🔙 Назад к фильтрам", callback_data="filter_back")]
                    ]
                )

                # If we have filtered by specific specializations, we want the booking flow to know about them
                # for the terminology fix.
                # Note: We'll actually handle this in start_booking by checking the specialist's profile directly
                # but we can also store the 'intended' specialization here.
                if trainer_profile.photo_url:
                    await message.answer_photo(trainer_profile.photo_url, caption=text, reply_markup=kb)
                else:
                    await message.answer(text, reply_markup=kb)

            # Pagination buttons
            pagination_buttons = []
            if page > 0:
                pagination_buttons.append(types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cat_page_{page-1}"))
            if offset + limit < total_count:
                pagination_buttons.append(types.InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"cat_page_{page+1}"))

            if pagination_buttons:
                await message.answer(
                    f"Страница {page+1} из {(total_count + limit - 1) // limit}",
                    reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[pagination_buttons])
                )

    if callback:
        await callback.answer()
