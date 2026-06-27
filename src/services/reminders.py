import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.models import Reminder, User, Booking, TrainerProfile, TimeSlot
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update
from aiogram import Bot
import asyncio
from src.utils.db import SessionLocal
from dateutil.tz import gettz, UTC

logger = logging.getLogger(__name__)

class ReminderService:
    @staticmethod
    async def schedule_reminders(session: AsyncSession, booking_id: int, user_id: int, start_time: datetime):
        """
        Creates reminder records for 24h and 2h before training.
        """
        now = datetime.utcnow()

        reminders = [
            ("24h", start_time - timedelta(hours=24)),
            ("2h", start_time - timedelta(hours=2))
        ]

        for r_type, scheduled_for in reminders:
            if scheduled_for > now:
                new_reminder = Reminder(
                    booking_id=booking_id,
                    user_id=user_id,
                    reminder_type=r_type,
                    scheduled_for=scheduled_for,
                    status="pending"
                )
                session.add(new_reminder)
                logger.info(f"Scheduled {r_type} reminder for user {user_id} at {scheduled_for}")
            else:
                logger.info(f"Skipping {r_type} reminder for user {user_id} (already in the past)")

    @staticmethod
    async def process_reminders(bot: Bot):
        """
        Background task to send pending reminders.
        """
        moscow_tz = gettz('Europe/Moscow')

        while True:
            try:
                now = datetime.utcnow()
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
                            booking_stmt = select(Booking).where(Booking.id == r.booking_id).options(selectinload(Booking.slot))
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

                            # Terminology based on type
                            time_text = "24 часа" if r.reminder_type == "24h" else "2 часа"

                            # Convert start time to Moscow for message
                            s_start = booking.start_time.replace(tzinfo=UTC).astimezone(moscow_tz)

                            msg = (
                                f"🔔 **Напоминание о записи!**\n\n"
                                f"До вашей записи к {trainer_name} осталось {time_text}.\n"
                                f"📅 Время: `{s_start.strftime('%d.%m %H:%M')}` (МСК)\n"
                                f"🏷 Услуга: `{booking.slot.format}`"
                            )

                            await bot.send_message(r.user_id, msg, parse_mode="Markdown")
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
