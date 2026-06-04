from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_role_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Я тренер"), KeyboardButton(text="Я клиент")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_trainer_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="📆 Расписание")],
            [KeyboardButton(text="👥 Мои клиенты"), KeyboardButton(text="💰 Финансы")],
            [KeyboardButton(text="📹 Контент"), KeyboardButton(text="📈 Статистика")]
        ],
        resize_keyboard=True
    )

def get_client_main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти тренера"), KeyboardButton(text="💳 Купить абонемент")],
            [KeyboardButton(text="📅 Мои занятия"), KeyboardButton(text="🏆 Рейтинг")],
            [KeyboardButton(text="🔥 Челленджи"), KeyboardButton(text="👥 Сообщество")]
        ],
        resize_keyboard=True
    )

def get_format_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Оффлайн"), KeyboardButton(text="Онлайн")],
            [KeyboardButton(text="Гибрид")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
