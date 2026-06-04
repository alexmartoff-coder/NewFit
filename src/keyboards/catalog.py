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
