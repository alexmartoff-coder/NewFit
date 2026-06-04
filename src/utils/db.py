import logging
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.utils.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Database engine and sessionmaker
engine = create_async_engine(settings.DATABASE_URL)

async def init_db(engine):
    """Создаёт таблицу specializations, если она не существует."""
    try:
        async with engine.connect() as conn:
            # SQL команда для создания таблицы
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS specializations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE
                )
            """))
            # Добавляем пару примеров, если таблица пустая
            await conn.execute(text("""
                INSERT INTO specializations (name)
                SELECT * FROM (VALUES ('силовые тренировки'), ('похудение и жиросжигание')) AS v(name)
                WHERE NOT EXISTS (SELECT 1 FROM specializations)
            """))
            await conn.commit()
            print("✅ Таблица specializations проверена/создана.")
    except Exception as e:
        print(f"⚠️ Ошибка при инициализации БД: {e}")

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def get_db():
    async with SessionLocal() as session:
        yield session
