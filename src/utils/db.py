import logging
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.utils.config import settings
from src.models.models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database engine and sessionmaker
engine = create_async_engine(settings.DATABASE_URL)

async def init_db(engine):
    """Создаёт все таблицы, если они не существуют."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with engine.connect() as conn:
            # Добавляем пару примеров, если таблица пустая
            await conn.execute(text("""
                INSERT INTO specializations (name)
                SELECT * FROM (VALUES ('силовые тренировки'), ('похудение и жиросжигание')) AS v(name)
                WHERE NOT EXISTS (SELECT 1 FROM specializations)
            """))
            await conn.commit()
        print("✅ Все таблицы базы данных проверены/созданы.")
    except Exception as e:
        print(f"⚠️ Ошибка при инициализации БД: {e}")

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def get_db():
    async with SessionLocal() as session:
        yield session
