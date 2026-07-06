import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.models import Reminder, User, Booking, TrainerProfile, TimeSlot
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from aiogram import Bot
import asyncio
from src.utils.db import SessionLocal
from dateutil.tz import gettz, UTC
from src.utils.text import escape_md

logger = logging.getLogger(__name__)

class ReminderService:
    @staticmethod
    async def schedule_reminders(session: AsyncSession, booking_id: int, client_user_id: int, trainer_user_id: int, start_time: datetime, end_time: datetime = None, is_online: bool = False):
        """
        Creates reminder records for 24h, 2h (and 10m for online) before training, and 10m after for review.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        reminders = [
            ("24h", start_time - timedelta(hours=24)),
            ("2h", start_time - timedelta(hours=2))
        ]

        if is_online:
            reminders.append(("10m", start_time - timedelta(minutes=10)))

        if end_time:
            reminders.append(("review", end_time + timedelta(minutes=10)))

        for r_type, scheduled_for in reminders:
            if scheduled_for > now:
                # Reminder for client
                session.add(Reminder(
                    booking_id=booking_id,
                    user_id=client_user_id,
                    reminder_type=r_type,
                    scheduled_for=scheduled_for,
                    status="pending"
                ))
                # Reminder for trainer (skip for review)
                if r_type != "review":
                    session.add(Reminder(
                        booking_id=booking_id,
                        user_id=trainer_user_id,
                        reminder_type=r_type,
                        scheduled_for=scheduled_for,
                        status="pending"
                    ))
                logger.info(f"Scheduled {r_type} reminder for client {client_user_id} and trainer {trainer_user_id} at {scheduled_for}")
            else:
                logger.info(f"Skipping {r_type} reminder (already in the past)")

    @staticmethod
    async def process_reminders(bot: Bot):
        """
        Background task to send pending reminders.
        """
        moscow_tz = gettz('Europe/Moscow')

        while True:
            try:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                async with SessionLocal() as session:
                    # Find pending reminders that are due
                    stmt = select(Reminder).where(
                        Reminder.status == "pending",
                        Reminder.scheduled_for <= now
                    )
                    res = await session.execute(stmt)
                    reminders = res.scalars().all()

                    if not reminders:
                        await asyncio.sleep(60)
                        continue

                    for r in reminders:
                        try:
                            # Fetch booking and trainer info
                            booking_stmt = select(Booking).where(Booking.id == r.booking_id).options(
                                selectinload(Booking.slot),
                                selectinload(Booking.client)
                            )
                            booking_res = await session.execute(booking_stmt)
                            booking = booking_res.scalar_one_or_none()

                            if not booking or booking.status == "canceled":
                                r.status = "canceled"
                                await session.commit()
                                continue

                            trainer_profile_stmt = select(TrainerProfile, User).join(User).where(TrainerProfile.id == booking.trainer_profile_id)
                            trainer_res = await session.execute(trainer_profile_stmt)
                            trainer_data = trainer_res.one_or_none()

                            trainer_name = "мастера"
                            if trainer_data:
                                trainer_name = trainer_data[1].full_name

                            client_name = booking.client.full_name or "Клиент"

                            # Terminology based on type
                            time_text = "24 часа" if r.reminder_type == "24h" else ("2 часа" if r.reminder_type == "2h" else "10 минут")

                            # Convert start time to Moscow for message
                            s_start = booking.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)

                            is_for_client = (r.user_id == booking.client.user_id)
                            if is_for_client:
                                recipient_msg = f"До вашей записи к {escape_md(trainer_name)} осталось {time_text}."
                            else:
                                recipient_msg = f"До вашей записи клиента {escape_md(client_name)} осталось {time_text}."

                            msg = (
                                f"🔔 **Напоминание о записи!**\n\n"
                                f"{recipient_msg}\n"
                                f"📅 Время: `{s_start.strftime('%d.%m %H:%M')}` (МСК)\n"
                                f"🏷 Услуга: `{escape_md(booking.slot.format)}`"
                            )

                            kb = None
                            if r.reminder_type == "review":
                                msg = (
                                    f"⭐ **Как прошло занятие?**\n\n"
                                    f"Ваше занятие с {escape_md(trainer_name)} завершилось. "
                                    f"Пожалуйста, оставьте отзыв, это поможет другим пользователям!"
                                )
                                kb = types.InlineKeyboardMarkup(inline_keyboard=[
                                    [types.InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"leave_review_{booking.id}")]
                                ])
                            elif r.reminder_type == "10m" and ("онлайн" in booking.slot.format.lower() or "online" in booking.slot.format.lower()):
                                if booking.slot.online_platform == "telegram":
                                    msg = "Занятие начинается через 10 минут."
                                    # Link to the other participant
                                    other_user_id = trainer_data[0].user_id if r.user_id == booking.client.user_id else booking.client.user_id
                                    kb = types.InlineKeyboardMarkup(inline_keyboard=[
                                        [types.InlineKeyboardButton(text="🎥 Начать видеозвонок", url=f"tg://user?id={other_user_id}")]
                                    ])
                                elif booking.slot.zoom_join_url:
                                    msg += f"\n\n🔗 **Ссылка на Zoom:** {booking.slot.zoom_join_url}"
                                    kb = types.InlineKeyboardMarkup(inline_keyboard=[
                                        [types.InlineKeyboardButton(text="🚀 Войти в Zoom", url=booking.slot.zoom_join_url)]
                                    ])

                            from aiogram import types
                            await bot.send_message(r.user_id, msg, reply_markup=kb, parse_mode="Markdown")
                            r.status = "sent"
                            logger.info(f"Sent {r.reminder_type} reminder to user {r.user_id}")

                        except Exception as e:
                            logger.error(f"Failed to send reminder {r.id}: {e}")
                            r.status = "failed"

                        await session.commit()

            except Exception as e:
                logger.error(f"Error in reminder worker: {e}")
                await asyncio.sleep(60)

            await asyncio.sleep(30)
