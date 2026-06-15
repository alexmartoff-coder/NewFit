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
            if "postgresql" in str(engine.url).lower():
                # Исправляем time_slots
                await conn.execute(text("ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_id_fkey"))
                await conn.execute(text("ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_profile_id_fkey"))
                await conn.execute(text("""
                    ALTER TABLE time_slots
                    ADD CONSTRAINT time_slots_trainer_profile_id_fkey
                    FOREIGN KEY (trainer_profile_id)
                    REFERENCES trainer_profiles(id)
                    ON DELETE CASCADE
                """))

                # Исправляем bookings (используем ADD COLUMN IF NOT EXISTS для надежности)
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS slot_id INTEGER"))

                # Переименовываем trainer_id в trainer_profile_id и меняем тип
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bookings' AND column_name='trainer_id') THEN
                            ALTER TABLE bookings RENAME COLUMN trainer_id TO trainer_profile_id;
                        END IF;
                    END $$;
                """))
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS trainer_profile_id INTEGER"))
                await conn.execute(text("ALTER TABLE bookings ALTER COLUMN trainer_profile_id TYPE INTEGER USING trainer_profile_id::integer"))

                # Исправляем client_profiles
                await conn.execute(text("ALTER TABLE client_profiles ADD COLUMN IF NOT EXISTS full_name VARCHAR(128)"))
                await conn.execute(text("ALTER TABLE client_profiles ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active'"))

                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS client_id INTEGER"))

                # Полная переустановка всех внешних ключей в таблице bookings (PostgreSQL)
                await conn.execute(text("""
                    DO $$
                    DECLARE
                        r RECORD;
                    BEGIN
                        -- 1. Удаляем все существующие FK в таблице bookings
                        FOR r IN (
                            SELECT conname
                            FROM pg_constraint
                            WHERE conrelid = 'bookings'::regclass AND contype = 'f'
                        )
                        LOOP
                            EXECUTE 'ALTER TABLE bookings DROP CONSTRAINT ' || quote_ident(r.conname);
                        END LOOP;

                        -- 2. Исправляем типы колонок
                        ALTER TABLE bookings ALTER COLUMN trainer_profile_id TYPE INTEGER USING trainer_profile_id::integer;
                        ALTER TABLE bookings ALTER COLUMN client_id TYPE INTEGER USING client_id::integer;
                        ALTER TABLE bookings ALTER COLUMN slot_id TYPE INTEGER USING slot_id::integer;

                        -- 3. Создаем правильные ключи заново
                        ALTER TABLE bookings ADD CONSTRAINT bookings_client_id_fkey FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE;
                        ALTER TABLE bookings ADD CONSTRAINT bookings_trainer_profile_id_fkey FOREIGN KEY (trainer_profile_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;
                        ALTER TABLE bookings ADD CONSTRAINT bookings_slot_id_fkey FOREIGN KEY (slot_id) REFERENCES time_slots(id) ON DELETE CASCADE;

                    EXCEPTION WHEN OTHERS THEN
                        RAISE NOTICE 'Skipping constraint recreation: %', SQLERRM;
                    END $$;
                """))

                # Исправляем reminders
                await conn.execute(text("ALTER TABLE reminders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'pending'"))
                await conn.execute(text("ALTER TABLE reminders ALTER COLUMN user_id TYPE BIGINT"))

                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS start_time TIMESTAMP WITHOUT TIME ZONE"))
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS end_time TIMESTAMP WITHOUT TIME ZONE"))

                # Попробуем заполнить пустые значения из связанных слотов
                await conn.execute(text("""
                    UPDATE bookings b
                    SET start_time = ts.start_time, end_time = ts.end_time
                    FROM time_slots ts
                    WHERE b.slot_id = ts.id AND (b.start_time IS NULL OR b.end_time IS NULL)
                """))

                await conn.execute(text("ALTER TABLE bookings ALTER COLUMN is_online DROP NOT NULL"))
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS status VARCHAR(50)"))

                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS price FLOAT"))
                await conn.execute(text("ALTER TABLE bookings ALTER COLUMN price TYPE FLOAT"))
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS paid BOOLEAN DEFAULT FALSE"))
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS client_notes TEXT"))
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS trainer_notes TEXT"))
                await conn.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS booked_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()"))

                # Добавляем UNIQUE для slot_id если его нет
                await conn.execute(text("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bookings_slot_id_key') THEN
                            ALTER TABLE bookings ADD CONSTRAINT bookings_slot_id_key UNIQUE (slot_id);
                        END IF;
                    END $$;
                """))

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
