from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_role_kb(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="Профи"), KeyboardButton(text="Клиент")],
        [KeyboardButton(text="❓ Узнать больше о NewFit")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)

def get_sphere_kb():
    kb = [
        [KeyboardButton(text="Фитнес"), KeyboardButton(text="Бьюти")],
        [KeyboardButton(text="Большой теннис"), KeyboardButton(text="Падл")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)

def get_trainer_main_kb(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="Мой профиль"), KeyboardButton(text="Моё расписание")],
        [KeyboardButton(text="Мои клиенты"), KeyboardButton(text="Статистика")],
        [KeyboardButton(text="Поддержка"), KeyboardButton(text="Инструкции")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_client_main_kb(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="Выбрать услугу")],
        [KeyboardButton(text="Мои записи"), KeyboardButton(text="💬 Мои диалоги")]
    ]
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

def get_spec_kb(selected_specs: list = None, role: str = "TRAINER"):
    if selected_specs is None:
        selected_specs = []

    if role == "BEAUTY":
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
    elif role == "TENNIS":
        specs = [
            ("Индивидуальные тренировки", "spec_indiv"),
            ("Групповые занятия", "spec_group"),
            ("Тренировки для детей", "spec_kids"),
            ("Подготовка к турнирам", "spec_tourn"),
            ("Спарринг", "spec_sparr"),
            ("Другое", "spec_other"),
        ]
    elif role == "PADEL":
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
