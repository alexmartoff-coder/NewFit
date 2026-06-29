import logging
from datetime import datetime, timedelta, timezone
import httpx
from sqlalchemy import select, and_
from src.models.models import Booking, TrainerSchedule, TimeSlot
from src.utils.db import SessionLocal

logger = logging.getLogger(__name__)

class CalendarService:
    @staticmethod
    async def get_google_access_token(session, schedule: TrainerSchedule):
        """Refreshes and returns a valid Google access token."""
        if schedule.token_expires_at and schedule.token_expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            return schedule.google_access_token

        # Refresh token logic
        payload = {
            'client_id': schedule.google_client_id,
            'client_secret': schedule.google_client_secret,
            'refresh_token': schedule.google_refresh_token,
            'grant_type': 'refresh_token',
        }

        async with httpx.AsyncClient() as client:
            response = await client.post('https://oauth2.googleapis.com/token', data=payload)
            if response.status_code == 200:
                data = response.json()
                schedule.google_access_token = data['access_token']
                schedule.token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=data['expires_in'])
                await session.commit()
                return schedule.google_access_token
            else:
                logger.error(f"Failed to refresh Google token for trainer {schedule.trainer_id}: {response.text}")
                return None

    @staticmethod
    async def add_event_to_google(trainer_id: int, booking_id: int):
        """Adds a booking event to the trainer's Google Calendar."""
        async with SessionLocal() as session:
            # 1. Get trainer schedule config
            stmt = select(TrainerSchedule).where(TrainerSchedule.trainer_id == trainer_id)
            res = await session.execute(stmt)
            schedule = res.scalar_one_or_none()

            if not schedule or not schedule.google_refresh_token or not schedule.sync_enabled:
                return

            # 2. Get booking details
            from sqlalchemy.orm import selectinload
            stmt_b = select(Booking).where(Booking.id == booking_id).options(
                selectinload(Booking.slot),
                selectinload(Booking.client)
            )
            res_b = await session.execute(stmt_b)
            booking = res_b.scalar_one_or_none()

            if not booking:
                return

            token = await CalendarService.get_google_access_token(session, schedule)
            if not token:
                return

            # 3. Create Google Event
            start_time = booking.start_time.isoformat()
            end_time = booking.end_time.isoformat()

            event = {
                'summary': f"NewFit: {booking.client.full_name or 'Клиент'}",
                'description': f"Услуга: {booking.slot.format}\nКлиент: {booking.client.full_name}\nЗапись через NewFit Bot",
                'start': {'dateTime': f"{start_time}Z", 'timeZone': schedule.timezone},
                'end': {'dateTime': f"{end_time}Z", 'timeZone': schedule.timezone},
            }

            if "онлайн" in booking.slot.format.lower() or "online" in booking.slot.format.lower():
                if booking.slot.zoom_join_url:
                    event['location'] = booking.slot.zoom_join_url
                else:
                    event['location'] = "Telegram Video"

            async with httpx.AsyncClient() as client:
                calendar_id = schedule.google_calendar_id or 'primary'
                url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
                headers = {'Authorization': f"Bearer {token}"}

                response = await client.post(url, json=event, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    # Store event ID back to slot
                    if booking.slot:
                        booking.slot.google_event_id = data.get('id')
                        await session.commit()
                    logger.info(f"Added Google event {data.get('id')} for trainer {trainer_id}")
                else:
                    logger.error(f"Failed to create Google event: {response.text}")

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
