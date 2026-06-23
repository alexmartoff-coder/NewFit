from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_filter_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📍 Город", callback_data="filter_city")],
            [InlineKeyboardButton(text="💪 Специализация", callback_data="filter_spec")],
            [InlineKeyboardButton(text="💰 Цена", callback_data="filter_price")],
            [InlineKeyboardButton(text="❌ Сбросить", callback_data="filter_reset")],
            [InlineKeyboardButton(text="✅ Показать", callback_data="filter_apply")]
        ]
    )

def get_price_filter_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Мин. цена", callback_data="price_min")],
            [InlineKeyboardButton(text="Макс. цена", callback_data="price_max")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="filter_back")]
        ]
    )

def get_catalog_city_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Москва", callback_data="cat_city_Москва")],
            [InlineKeyboardButton(text="Санкт-Петербург", callback_data="cat_city_Санкт-Петербург")],
            [InlineKeyboardButton(text="Онлайн", callback_data="cat_city_Онлайн")],
            [InlineKeyboardButton(text="Другой город", callback_data="filter_city")]
        ]
    )
