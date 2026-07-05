from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_launch_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Запустить бота")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_role_kb(is_admin: bool = False):
    kb = [
        [InlineKeyboardButton(text="Профи", callback_data="role_trainer"),
         InlineKeyboardButton(text="Клиент", callback_data="role_client")],
        [InlineKeyboardButton(text="❓ Узнать больше о NewFit", callback_data="learn_more")]
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="🛠 Админ", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_sphere_kb():
    kb = [
        [InlineKeyboardButton(text="Фитнес", callback_data="sphere_trainer"),
         InlineKeyboardButton(text="Бьюти", callback_data="sphere_beauty")],
        [InlineKeyboardButton(text="Большой теннис", callback_data="sphere_tennis"),
         InlineKeyboardButton(text="Падл", callback_data="sphere_padel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_trainer_main_kb(is_admin: bool = False, has_online: bool = False):
    kb = [
        [KeyboardButton(text="Мой профиль"), KeyboardButton(text="Моё расписание")],
        [KeyboardButton(text="Мои записи"), KeyboardButton(text="Мои клиенты")],
    ]
    if has_online is True:
        kb.append([KeyboardButton(text="🖥 Онлайн тренировка")])

    kb.extend([
        [KeyboardButton(text="Статистика"), KeyboardButton(text="Поддержка")],
        [KeyboardButton(text="Инструкции")]
    ])
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_client_main_kb(is_admin: bool = False, has_specialists: bool = False):
    kb = [
        [KeyboardButton(text="Выбрать услугу"), KeyboardButton(text="Мои записи")],
        [KeyboardButton(text="🖥 Онлайн тренировка")],
    ]

    if has_specialists:
        kb.append([KeyboardButton(text="Мои специалисты")])

    kb.append([KeyboardButton(text="💬 Мои диалоги")])

    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_format_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оффлайн занятия", callback_data="fmt_offline")],
            [InlineKeyboardButton(text="Онлайн занятия", callback_data="fmt_online")],
            [InlineKeyboardButton(text="Гибрид (оффлайн + онлайн)", callback_data="fmt_hybrid")]
        ]
    )

def get_spec_kb(selected_specs: list = None, role: str = "trainer"):
    if selected_specs is None:
        selected_specs = []

    # Extremely robust role normalization to lowercase string
    if hasattr(role, 'value'):
        r = str(role.value).lower()
    else:
        r = str(role).lower()

    if "userrole." in r:
        r = r.replace("userrole.", "")

    # Handle Russian labels if they were passed by mistake
    if r in ["бьюти", "beauty"]:
        r = "beauty"
    elif r in ["теннис", "большой теннис", "tennis"]:
        r = "tennis"
    elif r in ["падл", "padel"]:
        r = "padel"
    elif r in ["фитнес", "trainer", "fitness"]:
        r = "trainer"

    if r == "beauty":
        specs = [
            ("Маникюр", "spec_manicure"),
            ("Педикюр", "spec_pedicure"),
            ("Массаж", "spec_massage"),
            ("Косметология", "spec_cosmetology"),
            ("Парикмахерские услуги", "spec_hair"),
            ("Брови и ресницы", "spec_brows"),
            ("Макияж", "spec_makeup"),
            ("Другое", "spec_other"),
        ]
    elif r == "tennis":
        specs = [
            ("Индивидуальные тренировки", "spec_indiv"),
            ("Групповые занятия", "spec_group"),
            ("Тренировки для детей", "spec_kids"),
            ("Подготовка к турнирам", "spec_tourn"),
            ("Спарринг", "spec_sparr"),
            ("Другое", "spec_other"),
        ]
    elif r == "padel":
        specs = [
            ("Индивидуальные тренировки", "spec_indiv"),
            ("Групповые занятия", "spec_group"),
            ("Тренировки для детей", "spec_kids"),
            ("Подготовка к турнирам", "spec_tourn"),
            ("Спарринг", "spec_sparr"),
            ("Другое", "spec_other"),
        ]
    else:
        specs = [
            ("Силовые тренировки", "spec_strength"),
            ("Похудение и жиросжигание", "spec_weight_loss"),
            ("Функциональный тренинг", "spec_func"),
            ("Реабилитация и ОФП", "spec_rehab"),
            ("Кроссфит / HIIT", "spec_crossfit"),
            ("Тренировки для женщин/мужчин", "spec_gender"),
            ("Работа с подростками", "spec_teens"),
            ("Другое (свой вариант)", "spec_other"),
        ]

    kb = []
    for name, callback_data in specs:
        text = name
        if name in selected_specs:
            text = f"✅ {name}"
        kb.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    kb.append([InlineKeyboardButton(text="🚀 Готово", callback_data="spec_done")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def get_start_reg_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Начать регистрацию", callback_data="start_registration")]
        ]
    )

def get_city_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Москва"), KeyboardButton(text="Санкт-Петербург")],
            [KeyboardButton(text="Онлайн")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_district_kb(city: str):
    if city == "Москва":
        districts = [
            "ЦАО", "САО", "СВАО", "ВАО", "ЮВАО",
            "ЮАО", "ЮЗАО", "ЗАО", "СЗАО", "Зеленоград", "Новая Москва"
        ]
    elif city == "Санкт-Петербург":
        districts = [
            "Центральный", "Адмиралтейский", "Василеостровский", "Петроградский",
            "Выборгский", "Калининский", "Приморский", "Московский", "Фрунзенский",
            "Невский", "Кировский", "Красносельский", "Красногвардейский",
            "Пушкинский", "Петродворцовый", "Колпинский", "Курортный", "Кронштадтский"
        ]
    else:
        return None

    kb = []
    row = []
    for d in districts:
        row.append(KeyboardButton(text=d))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)
