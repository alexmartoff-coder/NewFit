from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_filter_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📍 Город/район", callback_data="filter_city")],
            [InlineKeyboardButton(text="📞 Телефон", callback_data="search_by_phone")],
            [InlineKeyboardButton(text="🔍 Никнейм", callback_data="search_by_username")],
            [InlineKeyboardButton(text="👤 ФИО", callback_data="search_by_name")],
            [InlineKeyboardButton(text="🔙 Назад к выбору услуги", callback_data="cat_back_to_start")]
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
