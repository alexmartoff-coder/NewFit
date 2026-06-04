from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_role_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👨‍🏫 Я тренер"), KeyboardButton(text="🏋️‍♀️ Я клиент")],
            [KeyboardButton(text="❓ Узнать больше о NewFit")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_trainer_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📅 Расписание и запись")],
            [KeyboardButton(text="👥 Мои клиенты"), KeyboardButton(text="💰 Финансы и выплаты")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="📹 Создать контент (рилсы)")],
            [KeyboardButton(text="🚀 Продвижение"), KeyboardButton(text="⭐ Повысить видимость")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Поддержка")],
            [KeyboardButton(text="📋 Инструкции")]
        ],
        resize_keyboard=True
    )

def get_client_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти тренера")],
            [KeyboardButton(text="📅 Мои занятия и абонементы"), KeyboardButton(text="🏆 Топ тренеров")],
            [KeyboardButton(text="🔥 Челленджи и мотивация"), KeyboardButton(text="👥 Сообщество NewFit")],
            [KeyboardButton(text="💬 Мои чаты с тренерами")]
        ],
        resize_keyboard=True
    )

def get_format_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оффлайн занятия", callback_data="fmt_offline")],
            [InlineKeyboardButton(text="Онлайн занятия", callback_data="fmt_online")],
            [InlineKeyboardButton(text="Гибрид (оффлайн + онлайн)", callback_data="fmt_hybrid")]
        ]
    )

def get_spec_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Силовые тренировки", callback_data="spec_strength")],
            [InlineKeyboardButton(text="Похудение и жиросжигание", callback_data="spec_weight_loss")],
            [InlineKeyboardButton(text="Функциональный тренинг", callback_data="spec_func")],
            [InlineKeyboardButton(text="Реабилитация и ОФП", callback_data="spec_rehab")],
            [InlineKeyboardButton(text="Кроссфит / HIIT", callback_data="spec_crossfit")],
            [InlineKeyboardButton(text="Тренировки для женщин/мужчин", callback_data="spec_gender")],
            [InlineKeyboardButton(text="Работа с подростками", callback_data="spec_teens")],
            [InlineKeyboardButton(text="Другое (свой вариант)", callback_data="spec_other")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="spec_done")]
        ]
    )

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
