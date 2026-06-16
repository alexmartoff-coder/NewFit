import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.models.models import Base, User, UserRole, ProfessionalProfile, WorkFormat

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
async def test_create_user(db_session):
    user = User(id=123, full_name="Test User", role=UserRole.CLIENT)
    db_session.add(user)
    await db_session.commit()

    db_user = await db_session.get(User, 123)
    assert db_user.full_name == "Test User"
    assert db_user.role == UserRole.CLIENT

@pytest.mark.asyncio
async def test_create_professional_profile(db_session):
    user = User(id=456, full_name="Trainer User", role=UserRole.TRAINER)
    db_session.add(user)
    await db_session.commit()

    profile = ProfessionalProfile(
        user_id=user.id,
        city="Moscow",
        experience=5,
        work_format=WorkFormat.HYBRID,
        price_single=2000.0,
        price_package=20000.0
    )
    db_session.add(profile)
    await db_session.commit()

    assert profile.id is not None
    assert profile.city == "Moscow"
    assert profile.work_format == WorkFormat.HYBRID
