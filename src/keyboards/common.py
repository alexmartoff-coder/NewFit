from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_role_kb(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="👨‍🏫 Я тренер"), KeyboardButton(text="🏋️‍♀️ Я клиент")],
        [KeyboardButton(text="❓ Узнать больше о NewFit")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)

def get_trainer_main_kb(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📅 Моё расписание")],
        [KeyboardButton(text="👥 Мои клиенты"), KeyboardButton(text="💰 Финансы и выплаты")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📹 Создать контент (рилсы)")],
        [KeyboardButton(text="🚀 Продвижение"), KeyboardButton(text="⭐ Повысить видимость")],
        [KeyboardButton(text="🔗 Подключить Google Календарь")],
        [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Поддержка")],
        [KeyboardButton(text="📋 Инструкции")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Админ")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_client_main_kb(is_admin: bool = False):
    kb = [
        [KeyboardButton(text="🔍 Найти тренера")],
        [KeyboardButton(text="📅 Мои занятия и абонементы"), KeyboardButton(text="🏆 Топ тренеров")],
        [KeyboardButton(text="🔥 Челленджи и мотивация"), KeyboardButton(text="👥 Сообщество NewFit")],
        [KeyboardButton(text="💬 Мои чаты с тренерами")]
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

def get_spec_kb(selected_specs: list = None):
    if selected_specs is None:
        selected_specs = []

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
