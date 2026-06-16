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
        # 1. Сначала создаем таблицы (отдельная транзакция)
        async with engine.begin() as conn:
            logger.info("Starting Base.metadata.create_all...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Base.metadata.create_all finished.")

        # 2. Применяем исправление схемы (только для PostgreSQL)
        if "postgresql" in str(engine.url).lower():
            logger.info("Applying PostgreSQL schema fixes...")
            async with engine.connect() as conn:
                # Вспомогательная функция для добавления колонки
                async def add_column_safe(table, col_name, col_type):
                    try:
                        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        await conn.commit()
                        # logger.info(f"Column {col_name} in {table} checked/added.")
                    except Exception as e:
                        logger.error(f"Error adding {col_name} to {table}: {e}")
                        await conn.rollback()

                # Исправляем time_slots FK
                try:
                    await conn.execute(text("ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_id_fkey"))
                    await conn.execute(text("ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_profile_id_fkey"))
                    await conn.execute(text("""
                        ALTER TABLE time_slots
                        ADD CONSTRAINT time_slots_trainer_profile_id_fkey
                        FOREIGN KEY (trainer_profile_id)
                        REFERENCES trainer_profiles(id)
                        ON DELETE CASCADE
                    """))
                    await conn.commit()
                except Exception:
                    await conn.rollback()

                # Исправляем bookings (колонки)
                await add_column_safe("bookings", "slot_id", "INTEGER")
                await add_column_safe("bookings", "trainer_profile_id", "INTEGER")
                await add_column_safe("bookings", "client_id", "BIGINT")
                await add_column_safe("bookings", "start_time", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("bookings", "end_time", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("bookings", "status", "VARCHAR(50)")
                await add_column_safe("bookings", "price", "FLOAT")
                await add_column_safe("bookings", "paid", "BOOLEAN DEFAULT FALSE")
                await add_column_safe("bookings", "client_notes", "TEXT")
                await add_column_safe("bookings", "trainer_notes", "TEXT")
                await add_column_safe("bookings", "booked_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")

                # Исправляем client_profiles
                await add_column_safe("client_profiles", "full_name", "VARCHAR(128)")
                await add_column_safe("client_profiles", "status", "VARCHAR(20) DEFAULT 'active'")

                # Исправляем trainer_schedules (ВСЕ КОЛОНКИ ОДНА ЗА ОДНОЙ)
                await add_column_safe("trainer_schedules", "google_client_id", "VARCHAR(200)")
                await add_column_safe("trainer_schedules", "google_client_secret", "VARCHAR(200)")
                await add_column_safe("trainer_schedules", "google_calendar_id", "VARCHAR(200)")
                await add_column_safe("trainer_schedules", "google_refresh_token", "TEXT")
                await add_column_safe("trainer_schedules", "google_access_token", "TEXT")
                await add_column_safe("trainer_schedules", "token_expires_at", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("trainer_schedules", "sync_enabled", "BOOLEAN DEFAULT TRUE")
                await add_column_safe("trainer_schedules", "timezone", "VARCHAR(50) DEFAULT 'Europe/Moscow'")
                await add_column_safe("trainer_schedules", "slot_duration", "INTEGER DEFAULT 60")
                await add_column_safe("trainer_schedules", "rolling_window", "INTEGER")
                await add_column_safe("trainer_schedules", "last_replenished", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("trainer_schedules", "updated_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")

                # Исправляем trainer_profiles
                await add_column_safe("trainer_profiles", "price_single", "FLOAT DEFAULT 0.0")
                await add_column_safe("trainer_profiles", "price_package", "FLOAT DEFAULT 0.0")
                await add_column_safe("trainer_profiles", "service_prices", "JSON")
                await add_column_safe("trainer_profiles", "rating", "FLOAT DEFAULT 5.0")
                await add_column_safe("trainer_profiles", "is_premium", "BOOLEAN DEFAULT FALSE")
                await add_column_safe("trainer_profiles", "status", "VARCHAR(20) DEFAULT 'approved'")

                # Исправляем time_slots (доп колонки)
                await add_column_safe("time_slots", "format", "VARCHAR(20) DEFAULT 'hybrid'")
                await add_column_safe("time_slots", "google_event_id", "VARCHAR(200)")
                await add_column_safe("time_slots", "notes", "TEXT")

                # Исправляем reminders
                await add_column_safe("reminders", "status", "VARCHAR(20) DEFAULT 'pending'")
                try:
                    await conn.execute(text("ALTER TABLE reminders ALTER COLUMN user_id TYPE BIGINT"))
                    await conn.commit()
                except Exception:
                    await conn.rollback()

                # Миграция данных bookings (сложная часть)
                try:
                    # Переименовываем trainer_id если он есть
                    await conn.execute(text("""
                        DO $$ BEGIN
                            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bookings' AND column_name='trainer_id') THEN
                                ALTER TABLE bookings RENAME COLUMN trainer_id TO trainer_profile_id;
                            END IF;
                        END $$;
                    """))

                    # Обеспечиваем SERIAL ID для client_profiles
                    await conn.execute(text("""
                        DO $$ BEGIN
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='client_profiles' AND column_name='id') THEN
                                ALTER TABLE client_profiles ADD COLUMN id SERIAL PRIMARY KEY;
                            END IF;
                        END $$;
                    """))

                    # Создаем профили клиентов для существующих записей
                    await conn.execute(text("""
                        INSERT INTO client_profiles (user_id, full_name, status)
                        SELECT DISTINCT client_id, 'Клиент', 'active'
                        FROM bookings WHERE client_id > 1000000
                        ON CONFLICT (user_id) DO NOTHING
                    """))

                    # Обновляем имена
                    await conn.execute(text("""
                        UPDATE client_profiles cp SET full_name = u.full_name
                        FROM users u WHERE cp.user_id = u.id
                        AND (cp.full_name IS NULL OR cp.full_name = 'None' OR cp.full_name = 'Клиент')
                    """))

                    # Мигрируем Telegram ID на internal ID в bookings
                    await conn.execute(text("""
                        UPDATE bookings b SET client_id = cp.id
                        FROM client_profiles cp WHERE b.client_id = cp.user_id AND b.client_id > 1000000;
                    """))

                    # Очищаем несмапленные
                    await conn.execute(text("UPDATE bookings SET client_id = NULL WHERE client_id > 1000000"))

                    # Меняем типы колонок
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN trainer_profile_id TYPE INTEGER USING trainer_profile_id::integer"))
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN client_id TYPE INTEGER USING client_id::integer"))
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN slot_id TYPE INTEGER USING slot_id::integer"))

                    # Восстанавливаем FK
                    await conn.execute(text("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_client_id_fkey"))
                    await conn.execute(text("ALTER TABLE bookings ADD CONSTRAINT bookings_client_id_fkey FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE"))

                    await conn.execute(text("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_trainer_profile_id_fkey"))
                    await conn.execute(text("ALTER TABLE bookings ADD CONSTRAINT bookings_trainer_profile_id_fkey FOREIGN KEY (trainer_profile_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE"))

                    await conn.execute(text("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_slot_id_fkey"))
                    await conn.execute(text("ALTER TABLE bookings ADD CONSTRAINT bookings_slot_id_fkey FOREIGN KEY (slot_id) REFERENCES time_slots(id) ON DELETE CASCADE"))

                    # Unique slot_id
                    await conn.execute(text("""
                        DO $$ BEGIN
                            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bookings_slot_id_key') THEN
                                ALTER TABLE bookings ADD CONSTRAINT bookings_slot_id_key UNIQUE (slot_id);
                            END IF;
                        END $$;
                    """))

                    # Drop is_online NOT NULL
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN is_online DROP NOT NULL"))

                    await conn.commit()
                except Exception as e:
                    logger.error(f"Error in complex migration: {e}")
                    await conn.rollback()

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
