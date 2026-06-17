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
        # 1. Применяем переименования таблиц и колонок ДО создания через Base.metadata.create_all
        if "postgresql" in str(engine.url).lower():
            async with engine.connect() as conn:
                # Таблицы
                tables_to_rename = [
                    ("trainer_profiles", "professional_profiles"),
                    ("trainer_schedules", "professional_schedules"),
                    ("schedule_templates", "professional_templates"),
                    ("trainer_specializations", "professional_specializations")
                ]
                for old_name, new_name in tables_to_rename:
                    try:
                        res = await conn.execute(text(f"SELECT 1 FROM pg_tables WHERE tablename = '{old_name}'"))
                        if res.scalar():
                            res_new = await conn.execute(text(f"SELECT 1 FROM pg_tables WHERE tablename = '{new_name}'"))
                            if not res_new.scalar():
                                logger.info(f"Renaming table {old_name} to {new_name}")
                                await conn.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                                await conn.commit()
                    except Exception as e:
                        logger.warning(f"Could not rename table {old_name}: {e}")
                        await conn.rollback()

                # Колонки
                columns_to_rename = [
                    ("time_slots", "trainer_profile_id", "professional_profile_id"),
                    ("bookings", "trainer_id", "professional_profile_id"),
                    ("bookings", "professional_id", "professional_profile_id"),
                    ("professional_schedules", "trainer_id", "professional_id"),
                    ("professional_templates", "trainer_id", "professional_id")
                ]
                for table, old_col, new_col in columns_to_rename:
                    try:
                        res = await conn.execute(text(f"SELECT 1 FROM information_schema.columns WHERE table_name='{table}' AND column_name='{old_col}'"))
                        if res.scalar():
                            res_new = await conn.execute(text(f"SELECT 1 FROM information_schema.columns WHERE table_name='{table}' AND column_name='{new_col}'"))
                            if not res_new.scalar():
                                logger.info(f"Renaming column {old_col} to {new_col} in table {table}")
                                await conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}"))
                                await conn.commit()
                            else:
                                # Both exist? We should probably drop the old one if it's causing NotNullViolation
                                logger.info(f"Both {old_col} and {new_col} exist in {table}. Dropping old {old_col} to avoid conflicts.")
                                await conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {old_col} DROP NOT NULL"))
                                await conn.execute(text(f"UPDATE {table} SET {new_col} = {old_col} WHERE {new_col} IS NULL"))
                                await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {old_col}"))
                                await conn.commit()
                    except Exception as e:
                        logger.warning(f"Could not process column rename/merge for {table}.{old_col}: {e}")
                        await conn.rollback()

        # 2. Создаем/обновляем таблицы
        async with engine.begin() as conn:
            logger.info("Starting Base.metadata.create_all...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Base.metadata.create_all finished.")

        # 3. Применяем исправление схемы (только для PostgreSQL)
        if "postgresql" in str(engine.url).lower():
            logger.info("Applying PostgreSQL schema fixes...")
            async with engine.connect() as conn:
                # Исправляем Enum UserRole
                try:
                    await conn.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'BEAUTY'"))
                    await conn.commit()
                except Exception as e:
                    await conn.rollback()
                    logger.warning(f"Could not add BEAUTY to userrole enum: {e}")

                # Вспомогательная функция для добавления колонки
                async def add_column_safe(table, col_name, col_type):
                    try:
                        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        await conn.commit()
                    except Exception as e:
                        logger.error(f"Error adding {col_name} to {table}: {e}")
                        await conn.rollback()

                # Обеспечиваем наличие критических колонок
                await add_column_safe("time_slots", "professional_profile_id", "INTEGER")
                await add_column_safe("bookings", "professional_profile_id", "INTEGER")
                await add_column_safe("professional_schedules", "professional_id", "BIGINT")
                await add_column_safe("professional_templates", "professional_id", "BIGINT")

                # Исправляем внешние ключи
                fk_script = """
                DO $$
                BEGIN
                    -- time_slots
                    BEGIN ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_id_fkey; EXCEPTION WHEN others THEN NULL; END;
                    BEGIN ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_trainer_profile_id_fkey; EXCEPTION WHEN others THEN NULL; END;
                    BEGIN ALTER TABLE time_slots DROP CONSTRAINT IF EXISTS time_slots_professional_profile_id_fkey; EXCEPTION WHEN others THEN NULL; END;

                    ALTER TABLE time_slots ADD CONSTRAINT time_slots_professional_profile_id_fkey
                    FOREIGN KEY (professional_profile_id) REFERENCES professional_profiles(id) ON DELETE CASCADE;

                    -- bookings
                    BEGIN ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_trainer_id_fkey; EXCEPTION WHEN others THEN NULL; END;
                    BEGIN ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_professional_id_fkey; EXCEPTION WHEN others THEN NULL; END;
                    BEGIN ALTER TABLE bookings DROP CONSTRAINT IF EXISTS bookings_professional_profile_id_fkey; EXCEPTION WHEN others THEN NULL; END;

                    ALTER TABLE bookings ADD CONSTRAINT bookings_professional_profile_id_fkey
                    FOREIGN KEY (professional_profile_id) REFERENCES professional_profiles(id) ON DELETE CASCADE;
                EXCEPTION WHEN others THEN
                    RAISE NOTICE 'FK update error: %', SQLERRM;
                END $$;
                """
                try:
                    await conn.execute(text(fk_script))
                    await conn.commit()
                except Exception as e:
                    logger.error(f"Error in FK updates: {e}")
                    await conn.rollback()

                # Прочие колонки
                await add_column_safe("bookings", "slot_id", "INTEGER")
                await add_column_safe("bookings", "client_id", "BIGINT")
                await add_column_safe("bookings", "start_time", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("bookings", "end_time", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("bookings", "status", "VARCHAR(50)")
                await add_column_safe("bookings", "price", "FLOAT")
                await add_column_safe("bookings", "paid", "BOOLEAN DEFAULT FALSE")
                await add_column_safe("bookings", "client_notes", "TEXT")
                await add_column_safe("bookings", "professional_notes", "TEXT")
                await add_column_safe("bookings", "booked_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")

                await add_column_safe("client_profiles", "full_name", "VARCHAR(128)")
                await add_column_safe("client_profiles", "status", "VARCHAR(20) DEFAULT 'active'")

                # professional_schedules columns
                for col in ["google_client_id", "google_client_secret", "google_calendar_id"]:
                    await add_column_safe("professional_schedules", col, "VARCHAR(200)")
                for col in ["google_refresh_token", "google_access_token"]:
                    await add_column_safe("professional_schedules", col, "TEXT")
                await add_column_safe("professional_schedules", "token_expires_at", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("professional_schedules", "sync_enabled", "BOOLEAN DEFAULT TRUE")
                await add_column_safe("professional_schedules", "timezone", "VARCHAR(50) DEFAULT 'Europe/Moscow'")
                await add_column_safe("professional_schedules", "slot_duration", "INTEGER DEFAULT 60")
                await add_column_safe("professional_schedules", "rolling_window", "INTEGER")
                await add_column_safe("professional_schedules", "last_replenished", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("professional_schedules", "updated_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")

                # professional_profiles columns
                await add_column_safe("professional_profiles", "price_single", "FLOAT DEFAULT 0.0")
                await add_column_safe("professional_profiles", "price_package", "FLOAT DEFAULT 0.0")
                await add_column_safe("professional_profiles", "service_prices", "JSON")
                await add_column_safe("professional_profiles", "rating", "FLOAT DEFAULT 5.0")
                await add_column_safe("professional_profiles", "is_premium", "BOOLEAN DEFAULT FALSE")
                await add_column_safe("professional_profiles", "status", "VARCHAR(20) DEFAULT 'approved'")

                # time_slots extra
                await add_column_safe("time_slots", "format", "VARCHAR(20) DEFAULT 'hybrid'")
                await add_column_safe("time_slots", "google_event_id", "VARCHAR(200)")
                await add_column_safe("time_slots", "notes", "TEXT")

                # Миграция данных клиентов
                try:
                    await conn.execute(text("""
                        DO $$ BEGIN
                            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='client_profiles' AND column_name='id') THEN
                                ALTER TABLE client_profiles ADD COLUMN id SERIAL PRIMARY KEY;
                            END IF;
                        END $$;
                    """))
                    await conn.execute(text("""
                        INSERT INTO client_profiles (user_id, full_name, status)
                        SELECT DISTINCT client_id, 'Клиент', 'active'
                        FROM bookings WHERE client_id > 1000000
                        ON CONFLICT (user_id) DO NOTHING
                    """))
                    await conn.execute(text("""
                        UPDATE client_profiles cp SET full_name = u.full_name
                        FROM users u WHERE cp.user_id = u.id
                        AND (cp.full_name IS NULL OR cp.full_name = 'None' OR cp.full_name = 'Клиент')
                    """))
                    await conn.execute(text("""
                        UPDATE bookings b SET client_id = cp.id
                        FROM client_profiles cp WHERE b.client_id = cp.user_id AND b.client_id > 1000000;
                    """))
                    await conn.execute(text("UPDATE bookings SET client_id = NULL WHERE client_id > 1000000"))
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN professional_profile_id TYPE INTEGER USING professional_profile_id::integer"))
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN client_id TYPE INTEGER USING client_id::integer"))
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN slot_id TYPE INTEGER USING slot_id::integer"))

                    # Drop is_online and trainer_notes if they still exist under old names
                    try:
                        await conn.execute(text("ALTER TABLE bookings ALTER COLUMN is_online DROP NOT NULL"))
                    except Exception: pass

                    await conn.commit()
                except Exception as e:
                    logger.error(f"Data migration error: {e}")
                    await conn.rollback()

        async with engine.connect() as conn:
            # Добавляем список специализаций
            specs = [
                'Силовые тренировки', 'Похудение и жиросжигание', 'Функциональный тренинг',
                'Реабилитация и ОФП', 'Кроссфит / HIIT', 'Тренировки для женщин/мужчин',
                'Работа с подростками', 'Маникюр', 'Педикюр', 'Массаж', 'Косметология',
                'Парикмахерские услуги', 'Брови и ресницы', 'Макияж', 'Другое'
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
