import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.models.models import Base, User, UserRole, TrainerProfile, WorkFormat, TimeSlot, Booking

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session

    await engine.dispose()

@pytest.mark.asyncio
async def test_create_booking_with_times(db_session):
    # Setup trainer
    trainer_user = User(id=1, full_name="Trainer", role=UserRole.TRAINER)
    db_session.add(trainer_user)
    await db_session.commit()

    profile = TrainerProfile(
        user_id=trainer_user.id,
        city="Moscow",
        work_format=WorkFormat.HYBRID
    )
    db_session.add(profile)
    await db_session.commit()

    # Setup client
    client_user = User(id=2, full_name="Client", role=UserRole.CLIENT)
    db_session.add(client_user)
    await db_session.commit()

    # Setup slot
    start_time = datetime.utcnow() + timedelta(hours=1)
    end_time = start_time + timedelta(hours=1)
    slot = TimeSlot(
        trainer_profile_id=profile.id,
        start_time=start_time,
        end_time=end_time,
        status="free",
        price=1000.0
    )
    db_session.add(slot)
    await db_session.commit()

    # Create booking
    booking = Booking(
        slot_id=slot.id,
        trainer_profile_id=profile.id,
        client_id=client_user.id,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status="confirmed",
        price=slot.price
    )
    db_session.add(booking)
    await db_session.commit()

    # Verify
    db_booking = await db_session.get(Booking, booking.id)
    assert db_booking.start_time == start_time
    assert db_booking.end_time == end_time
    assert db_booking.status == "confirmed"
