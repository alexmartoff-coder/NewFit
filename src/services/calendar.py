from datetime import datetime, timedelta
from src.models.models import Booking
from src.utils.db import SessionLocal
from sqlalchemy import select, and_

class CalendarService:
    @staticmethod
    async def is_available(trainer_profile_id: int, start_time: datetime, end_time: datetime):
        async with SessionLocal() as session:
            query = select(Booking).where(
                Booking.trainer_profile_id == trainer_profile_id,
                Booking.status != "cancelled",
                and_(
                    Booking.start_time < end_time,
                    Booking.end_time > start_time
                )
            )
            result = await session.execute(query)
            return result.scalar_one_or_none() is None

    @staticmethod
    async def create_booking(trainer_profile_id: int, client_id: int, start_time: datetime, duration_minutes: int = 60):
        async with SessionLocal() as session:
            end_time = start_time + timedelta(minutes=duration_minutes)
            booking = Booking(
                trainer_profile_id=trainer_profile_id,
                client_id=client_id,
                start_time=start_time,
                end_time=end_time
            )
            session.add(booking)
            await session.commit()
            return booking

    @staticmethod
    async def get_trainer_schedule(trainer_profile_id: int, date: datetime):
        async with SessionLocal() as session:
            start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

            query = select(Booking).where(
                Booking.trainer_profile_id == trainer_profile_id,
                Booking.start_time >= start_of_day,
                Booking.start_time < end_of_day
            )
            result = await session.execute(query)
            return result.scalars().all()
