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
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(db_url)

async def init_db(engine):
    """Создаёт все таблицы, если они не существуют, и применяет необходимые исправления схемы."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Применяем исправление схемы только для PostgreSQL
            if "postgresql" in str(engine.url):
                fix_sql = """
                DO $$
                BEGIN
                    -- 1. Удаляем старый некорректный ключ, если он существует
                    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'time_slots_trainer_id_fkey') THEN
                        ALTER TABLE time_slots DROP CONSTRAINT time_slots_trainer_id_fkey;
                    END IF;

                    -- 2. Убеждаемся, что trainer_profile_id ссылается на trainer_profiles(id), а не на users(id)
                    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'time_slots_trainer_profile_id_fkey') THEN
                         ALTER TABLE time_slots DROP CONSTRAINT time_slots_trainer_profile_id_fkey;
                    END IF;

                    ALTER TABLE time_slots
                    ADD CONSTRAINT time_slots_trainer_profile_id_fkey
                    FOREIGN KEY (trainer_profile_id)
                    REFERENCES trainer_profiles(id)
                    ON DELETE CASCADE;

                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Ошибка при обновлении схемы: %', SQLERRM;
                END $$;
                """
                await conn.execute(text(fix_sql))

        async with engine.connect() as conn:
            # Добавляем список специализаций, если их еще нет
            specs = [
                'Силовые тренировки',
                'Похудение и жиросжигание',
                'Функциональный тренинг',
                'Реабилитация и ОФП',
                'Кроссфит / HIIT',
                'Тренировки для женщин/мужчин',
                'Работа с подростками',
                'Другое'
            ]
            for spec in specs:
                await conn.execute(
                    text("INSERT INTO specializations (name) VALUES (:name) ON CONFLICT (name) DO NOTHING"),
                    {"name": spec}
                )
            await conn.commit()
        print("✅ Все таблицы базы данных проверены/созданы и исправлены.")
    except Exception as e:
        print(f"⚠️ Ошибка при инициализации БД: {e}")

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def get_db():
    async with SessionLocal() as session:
        yield session
