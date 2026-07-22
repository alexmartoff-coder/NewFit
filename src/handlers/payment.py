import logging
import uuid
import httpx
from aiogram import Router, types, F
from sqlalchemy import select

from src.utils.config import settings
from src.utils.db import SessionLocal
from src.models.models import TrainerProfile

logger = logging.getLogger(__name__)
router = Router()

async def create_subscription_payment(user_id: int) -> dict:
    """
    Создание платежа для подписки (4990 ₽/мес) в ЮKassa.
    Если учетные данные не настроены или YOOKASSA_TEST_MODE = True,
    возвращается тестовый/имитационный объект платежа.
    """
    shop_id = settings.YOOKASSA_SHOP_ID
    secret_key = settings.YOOKASSA_SECRET_KEY
    test_mode = settings.YOOKASSA_TEST_MODE

    # Если учетные данные пустые, фиктивные или включен тестовый режим, отдаем имитацию ссылки
    if not shop_id or not secret_key or shop_id == "dummy" or secret_key == "dummy" or test_mode:
        mock_id = f"mock_sub_{uuid.uuid4().hex[:8]}"
        return {
            "id": mock_id,
            "confirmation_url": f"https://checkout.yookassa.ru/payment/mock_sub_{user_id}_4990",
            "is_mock": True
        }

    # Настоящий запрос к API ЮKassa
    url = "https://api.yookassa.ru/v3/payments"
    headers = {
        "Idempotence-Key": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }
    payload = {
        "amount": {
            "value": "4990.00",
            "currency": "RUB"
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/newfit_workout_bot"
        },
        "description": "Подписка NewFit (4990 ₽/мес)",
        "metadata": {
            "user_id": str(user_id),
            "type": "subscription"
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
                auth=(shop_id, secret_key),
                timeout=10.0
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "id": data.get("id"),
                    "confirmation_url": data.get("confirmation", {}).get("confirmation_url"),
                    "is_mock": False
                }
            else:
                logger.error(f"YooKassa API response error: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Exception calling YooKassa API: {e}")

    # Фолбек на имитацию при любых ошибках
    mock_id = f"mock_sub_{uuid.uuid4().hex[:8]}"
    return {
        "id": mock_id,
        "confirmation_url": f"https://checkout.yookassa.ru/payment/mock_sub_{user_id}_4990",
        "is_mock": True
    }

async def payment_webhook(request_json: dict) -> bool:
    """
    Обработчик успешного платежа (payment_webhook).
    Регистрирует активацию подписки при получении события payment.succeeded.
    """
    event = request_json.get("event")
    payment_obj = request_json.get("object", {})
    status = payment_obj.get("status")

    if event == "payment.succeeded" or status == "succeeded":
        metadata = payment_obj.get("metadata", {})
        user_id_str = metadata.get("user_id")
        payment_type = metadata.get("type")

        if user_id_str and payment_type == "subscription":
            user_id = int(user_id_str)
            async with SessionLocal() as session:
                stmt = select(TrainerProfile).where(TrainerProfile.user_id == user_id)
                res = await session.execute(stmt)
                profile = res.scalar_one_or_none()
                if profile:
                    profile.is_subscribed = True
                    await session.commit()
                    logger.info(f"Subscription (4990 RUB) activated for user_id={user_id} via webhook.")
                    return True
    return False

# ----- Bot UI Handlers -----

@router.callback_query(F.data == "pay_sub_4990")
async def process_sub_payment_request(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    payment_info = await create_subscription_payment(user_id)
    url = payment_info.get("confirmation_url")

    # Формируем клавиатуру
    buttons = [
        [types.InlineKeyboardButton(text="💳 Оплатить 4990 ₽", url=url)]
    ]

    # Если платеж имитационный/тестовый, добавляем кнопку для мгновенного подтверждения
    if payment_info.get("is_mock"):
        buttons.append([
            types.InlineKeyboardButton(
                text="🤖 Подтвердить оплату (Тест)",
                callback_data=f"verify_mock_sub_{user_id}"
            )
        ])

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    text = (
        "💳 **Оплата подписки NewFit**\n\n"
        "Стоимость: 4990 ₽ в месяц.\n"
        "Подписка необходима для продолжения работы с вашей базой клиентов и расписанием при достижении лимита в 10 клиентов.\n\n"
        "Пожалуйста, произведите оплату по ссылке ниже:"
    )

    if callback.message.photo:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("verify_mock_sub_"))
async def verify_mock_sub_payment(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[3])

    # Имитируем успешное срабатывание вебхука
    webhook_payload = {
        "event": "payment.succeeded",
        "object": {
            "status": "succeeded",
            "metadata": {
                "user_id": str(user_id),
                "type": "subscription"
            }
        }
    }

    success = await payment_webhook(webhook_payload)
    if success:
        text = "🎉 **Подписка успешно активирована!**\n\nСпасибо за оплату подписки NewFit. Теперь вы можете без ограничений просматривать список клиентов и работать с записями."
        if callback.message.photo:
            await callback.message.edit_caption(caption=text)
        else:
            await callback.message.edit_text(text=text)
    else:
        await callback.answer("Не удалось активировать подписку. Попробуйте еще раз.")
