from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_role_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Я тренер"), KeyboardButton(text="Я клиент")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
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
