import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.models import Reminder

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
