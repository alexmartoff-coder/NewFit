from aiogram import Router, types, F
from src.services.payments import PaymentService
from src.models.models import Subscription, User, ClientProfile
from src.utils.db import SessionLocal
from src.keyboards.inline import add_admin_button
from sqlalchemy import select

router = Router()

@router.message(F.text == "💳 Купить абонемент")
async def show_subscription_packages(message: types.Message, is_admin: bool = False):
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="8 занятий - 15 000₽", callback_data="buy_sub_8_15000")],
            [types.InlineKeyboardButton(text="12 занятий - 20 000₽", callback_data="buy_sub_12_20000")],
            [types.InlineKeyboardButton(text="24 занятия - 35 000₽", callback_data="buy_sub_24_35000")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    await message.answer("Выберите пакет абонементов:", reply_markup=kb)

@router.callback_query(F.data.startswith("buy_sub_"))
async def process_sub_purchase(callback: types.CallbackQuery, is_admin: bool = False):
    _, _, count, price = callback.data.split("_")
    count = int(count)
    price = float(price)

    payment_link = await PaymentService.create_payment_link(
        amount=price,
        description=f"Абонемент на {count} занятий",
        user_id=callback.from_user.id
    )

    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="Оплатить", url=payment_link)],
            [types.InlineKeyboardButton(text="Проверить оплату (Mock)", callback_data=f"verify_sub_{count}_{price}")]
        ]
    )
    kb = add_admin_button(kb, is_admin=is_admin)
    text = f"Вы выбрали пакет на {count} занятий за {price}₽.\nОплатите по ссылке ниже:"
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb)
    else:
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data.startswith("verify_sub_"))
async def verify_sub_mock(callback: types.CallbackQuery):
    _, _, count, price = callback.data.split("_")
    count = int(count)

    async with SessionLocal() as session:
        stmt = select(ClientProfile.id).where(ClientProfile.user_id == callback.from_user.id)
        res = await session.execute(stmt)
        client_id = res.scalar_one()

        # Here we mock a trainer selection for the sub.
        # In reality, subs are usually per-trainer or platform-wide.
        # For now, let's assume it's for a "platform" trainer or just a general sub.
        sub = Subscription(
            client_id=client_id,
            trainer_id=1, # Mock trainer ID
            total_sessions=count,
            remaining_sessions=count
        )
        session.add(sub)
        await session.commit()

    text = f"Оплата подтверждена! Вам начислено {count} занятий."
    if callback.message.photo:
        await callback.message.edit_caption(caption=text)
    else:
        await callback.message.edit_text(text)
    await callback.answer()
