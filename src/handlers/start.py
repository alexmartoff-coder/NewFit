from aiogram import Router, types, F
from aiogram.filters import CommandStart
from src.keyboards.common import get_role_kb

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать в NewFit! Выберите вашу роль:",
        reply_markup=get_role_kb()
    )
