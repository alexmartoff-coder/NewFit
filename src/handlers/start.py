from aiogram import Router, types, F
from aiogram.filters import CommandStart
from src.keyboards.common import get_role_kb

router = Router()

@router.message(CommandStart())
@router.message(F.text == "/menu")
async def cmd_start(message: types.Message):
    await message.answer(
        "Добро пожаловать в NewFit — экосистему для фитнеса будущего! 🔥\n\n"
        "Здесь тренеры находят клиентов, а клиенты — лучших тренеров.\n\n"
        "Выберите свою роль:",
        reply_markup=get_role_kb()
    )

@router.message(F.text == "❓ Узнать больше о NewFit")
async def learn_more(message: types.Message):
    await message.answer(
        "NewFit — это единая экосистема для фитнес-тренеров и клиентов в Telegram.\n"
        "Мы помогаем тренерам автоматизировать запись, а клиентам — быстро находить профессионалов."
    )

@router.message(F.text == "/help")
async def cmd_help(message: types.Message):
    await message.answer("Служба поддержки NewFit: @NewFitSupport")
