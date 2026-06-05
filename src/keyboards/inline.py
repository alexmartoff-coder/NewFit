from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional

def add_admin_button(keyboard: Optional[InlineKeyboardMarkup] = None, is_admin: bool = False) -> Optional[InlineKeyboardMarkup]:
    """Добавляет кнопку админа в конец существующей клавиатуры (или создает новую)"""
    if not is_admin:
        return keyboard

    if keyboard is None:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛠 Админ", callback_data="admin_panel")]])

    # Копируем существующие кнопки
    new_keyboard = list(keyboard.inline_keyboard)

    # Проверяем, нет ли уже такой кнопки (по callback_data)
    for row in new_keyboard:
        for button in row:
            if hasattr(button, "callback_data") and button.callback_data == "admin_panel":
                return keyboard

    # Добавляем кнопку админа в отдельном ряду
    new_keyboard.append([InlineKeyboardButton(text="🛠 Админ", callback_data="admin_panel")])

    return InlineKeyboardMarkup(inline_keyboard=new_keyboard)
