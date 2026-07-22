import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.models.models import Base, User, UserRole, TrainerProfile, WorkFormat
from src.handlers.payment import create_subscription_payment, payment_webhook
from src.utils.config import settings

DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session(monkeypatch):
    # Setup test database and engine
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Use monkeypatch or custom session logic so PaymentService uses the test DB SessionLocal
    SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("src.handlers.payment.SessionLocal", SessionLocal)

    async with SessionLocal() as session:
        yield session

    await engine.dispose()

@pytest.mark.asyncio
async def test_create_subscription_payment_mock():
    # Test with settings configured for mock (either YOOKASSA_TEST_MODE = True or default)
    res = await create_subscription_payment(12345)
    assert res is not None
    assert "confirmation_url" in res
    assert res["is_mock"] is True
    assert "mock_sub_12345_4990" in res["confirmation_url"]

@pytest.mark.asyncio
async def test_payment_webhook_succeeded(db_session):
    # Create trainer
    trainer_user = User(id=123, full_name="Sub Trainer", role=UserRole.TRAINER)
    db_session.add(trainer_user)
    await db_session.commit()

    profile = TrainerProfile(
        user_id=trainer_user.id,
        city="Moscow",
        work_format=WorkFormat.HYBRID,
        is_subscribed=False
    )
    db_session.add(profile)
    await db_session.commit()

    # Create mock payment webhook payload
    payload = {
        "event": "payment.succeeded",
        "object": {
            "status": "succeeded",
            "metadata": {
                "user_id": "123",
                "type": "subscription"
            }
        }
    }

    # Execute webhook handler
    success = await payment_webhook(payload)
    assert success is True

    # Check updated DB state
    await db_session.refresh(profile)
    assert profile.is_subscribed is True
    assert profile.subscription_expires_at is not None

    from datetime import datetime, timedelta, timezone
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    assert profile.subscription_expires_at > now_utc
    assert profile.subscription_expires_at < now_utc + timedelta(days=31)
