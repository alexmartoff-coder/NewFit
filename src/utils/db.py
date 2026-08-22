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

async def execute_sql_safe(engine, sql_str: str, params: dict = None):
    """Executes a single SQL statement in an isolated transaction to prevent InFailedSQLTransactionError."""
    try:
        async with engine.begin() as conn:
            return await conn.execute(text(sql_str), params or {})
    except Exception as e:
        logger.warning(f"Safe SQL execution failed for [{sql_str.strip()[:60]}...]: {e}")
        return None

async def add_column_safe(engine, table: str, col_name: str, col_type: str):
    """Adds a column safely in an isolated transaction."""
    sql_str = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
    await execute_sql_safe(engine, sql_str)

async def init_db(engine):
    """Создаёт все таблицы, если они не существуют, и применяет необходимые исправления схемы."""
    try:
        is_postgres = "postgresql" in str(engine.url).lower()
        is_sqlite = "sqlite" in str(engine.url).lower()

        # 0. PostgreSQL absolute first fixes
        if is_postgres:
            await execute_sql_safe(engine, "ALTER TABLE specializations ALTER COLUMN name TYPE VARCHAR(100)")

        # 1. Применяем переименования таблиц и колонок ДО создания через Base.metadata.create_all
        if is_postgres:
            tables_to_rename = [
                ("professional_profiles", "trainer_profiles"),
                ("professional_schedules", "trainer_schedules"),
                ("professional_templates", "schedule_templates"),
                ("professional_specializations", "trainer_specializations")
            ]
            for old_name, new_name in tables_to_rename:
                try:
                    res = await execute_sql_safe(engine, f"SELECT 1 FROM pg_tables WHERE tablename = '{old_name}'")
                    if res and res.scalar():
                        res_new = await execute_sql_safe(engine, f"SELECT 1 FROM pg_tables WHERE tablename = '{new_name}'")
                        if res_new and not res_new.scalar():
                            logger.info(f"Renaming table {old_name} back to {new_name}")
                            await execute_sql_safe(engine, f"ALTER TABLE {old_name} RENAME TO {new_name}")
                except Exception as e:
                    logger.warning(f"Could not rename table {old_name}: {e}")

            columns_to_rename = [
                ("time_slots", "professional_profile_id", "trainer_profile_id"),
                ("bookings", "professional_profile_id", "trainer_profile_id"),
                ("trainer_schedules", "professional_id", "trainer_id"),
                ("schedule_templates", "professional_id", "trainer_id")
            ]
            for table, old_col, new_col in columns_to_rename:
                try:
                    res = await execute_sql_safe(engine, f"SELECT 1 FROM information_schema.columns WHERE table_name='{table}' AND column_name='{old_col}'")
                    if res and res.scalar():
                        res_new = await execute_sql_safe(engine, f"SELECT 1 FROM information_schema.columns WHERE table_name='{table}' AND column_name='{new_col}'")
                        if res_new and not res_new.scalar():
                            logger.info(f"Renaming column {old_col} to {new_col} in table {table}")
                            await execute_sql_safe(engine, f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}")
                        else:
                            logger.info(f"Both {old_col} and {new_col} exist in {table}. Dropping old {old_col} to avoid conflicts.")
                            await execute_sql_safe(engine, f"ALTER TABLE {table} ALTER COLUMN {old_col} DROP NOT NULL")
                            await execute_sql_safe(engine, f"UPDATE {table} SET {new_col} = {old_col} WHERE {new_col} IS NULL")
                            await execute_sql_safe(engine, f"ALTER TABLE {table} DROP COLUMN {old_col}")
                except Exception as e:
                    logger.warning(f"Could not process column rename/merge for {table}.{old_col}: {e}")

        # Fix for SQLite
        if is_sqlite:
            try:
                res = await execute_sql_safe(engine, "PRAGMA table_info('time_slots')")
                if res:
                    cols = [c[1] for c in res.fetchall()]
                    if "professional_profile_id" in cols and "trainer_profile_id" not in cols:
                        logger.info("Renaming professional_profile_id to trainer_profile_id in SQLite")
                        await execute_sql_safe(engine, "ALTER TABLE time_slots RENAME COLUMN professional_profile_id TO trainer_profile_id")
                    elif "professional_profile_id" in cols and "trainer_profile_id" in cols:
                        await execute_sql_safe(engine, "ALTER TABLE time_slots DROP COLUMN professional_profile_id")

                res2 = await execute_sql_safe(engine, "PRAGMA table_info('trainer_profiles')")
                if res2:
                    cols2 = [c[1] for c in res2.fetchall()]
                    if "is_subscribed" not in cols2 and len(cols2) > 0:
                        logger.info("Adding column is_subscribed to trainer_profiles in SQLite")
                        await execute_sql_safe(engine, "ALTER TABLE trainer_profiles ADD COLUMN is_subscribed BOOLEAN DEFAULT FALSE")
                    if "subscription_expires_at" not in cols2 and len(cols2) > 0:
                        logger.info("Adding column subscription_expires_at to trainer_profiles in SQLite")
                        await execute_sql_safe(engine, "ALTER TABLE trainer_profiles ADD COLUMN subscription_expires_at TIMESTAMP")
            except Exception as e:
                logger.warning(f"SQLite migration error: {e}")

        # 2. Создаем/обновляем таблицы
        try:
            async with engine.begin() as conn:
                logger.info("Starting Base.metadata.create_all...")
                await conn.run_sync(Base.metadata.create_all)
                logger.info("Base.metadata.create_all finished.")
        except Exception as e:
            logger.warning(f"Error in Base.metadata.create_all: {e}")

        # 3. Применяем исправление схемы (только для PostgreSQL)
        if is_postgres:
            logger.info("Applying PostgreSQL schema fixes in isolated transactions...")

            # ALTER TYPE ... ADD VALUE cannot run inside a multi-statement transaction
            for val in ['beauty', 'tennis', 'padel', 'trainer', 'client', 'admin']:
                await execute_sql_safe(engine, f"ALTER TYPE userrole ADD VALUE IF NOT EXISTS '{val}'")

            # Update role values
            await execute_sql_safe(engine, "UPDATE users SET role = 'beauty' WHERE role = 'BEAUTY'")
            await execute_sql_safe(engine, "UPDATE users SET role = 'tennis' WHERE role = 'TENNIS'")
            await execute_sql_safe(engine, "UPDATE users SET role = 'padel' WHERE role = 'PADEL'")
            await execute_sql_safe(engine, "UPDATE users SET role = 'trainer' WHERE role = 'TRAINER'")
            await execute_sql_safe(engine, "UPDATE users SET role = 'client' WHERE role = 'CLIENT'")
            await execute_sql_safe(engine, "UPDATE users SET role = 'admin' WHERE role = 'ADMIN'")

            await execute_sql_safe(engine, "ALTER TABLE specializations ALTER COLUMN name TYPE VARCHAR(100)")

            await add_column_safe(engine, "time_slots", "trainer_profile_id", "INTEGER")
            await add_column_safe(engine, "bookings", "trainer_profile_id", "INTEGER")
            await add_column_safe(engine, "trainer_schedules", "trainer_id", "BIGINT")
            await add_column_safe(engine, "schedule_templates", "trainer_id", "BIGINT")

            # Unique constraints for ON CONFLICT before migration
            await execute_sql_safe(engine, """
                DELETE FROM specializations WHERE id NOT IN (
                    SELECT MIN(id) FROM specializations GROUP BY name
                )
            """)
            await execute_sql_safe(engine, "ALTER TABLE specializations DROP CONSTRAINT IF EXISTS specializations_name_key")
            await execute_sql_safe(engine, "ALTER TABLE specializations ADD CONSTRAINT specializations_name_key UNIQUE (name)")

            await execute_sql_safe(engine, """
                DELETE FROM client_profiles WHERE id NOT IN (
                    SELECT MIN(id) FROM client_profiles GROUP BY user_id
                )
            """)
            await execute_sql_safe(engine, "ALTER TABLE client_profiles DROP CONSTRAINT IF EXISTS client_profiles_user_id_key")
            await execute_sql_safe(engine, "ALTER TABLE client_profiles ADD CONSTRAINT client_profiles_user_id_key UNIQUE (user_id)")

            # Foreign key repair script
            fk_script = """
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT constraint_name, table_name
                          FROM information_schema.table_constraints
                          WHERE constraint_type = 'FOREIGN KEY'
                          AND table_schema = 'public')
                LOOP
                    EXECUTE 'ALTER TABLE public.' || quote_ident(r.table_name) || ' DROP CONSTRAINT ' || quote_ident(r.constraint_name);
                END LOOP;

                ALTER TABLE trainer_profiles ADD CONSTRAINT trainer_profiles_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

                ALTER TABLE client_profiles ADD CONSTRAINT client_profiles_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

                ALTER TABLE trainer_schedules ADD CONSTRAINT trainer_schedules_trainer_id_fkey
                FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE;

                ALTER TABLE schedule_templates ADD CONSTRAINT schedule_templates_trainer_id_fkey
                FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE;

                ALTER TABLE trainer_specializations ADD CONSTRAINT trainer_specializations_trainer_id_fkey
                FOREIGN KEY (trainer_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                ALTER TABLE trainer_specializations ADD CONSTRAINT trainer_specializations_spec_id_fkey
                FOREIGN KEY (specialization_id) REFERENCES specializations(id) ON DELETE CASCADE;

                ALTER TABLE time_slots ADD CONSTRAINT time_slots_trainer_profile_id_fkey
                FOREIGN KEY (trainer_profile_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                ALTER TABLE bookings ADD CONSTRAINT bookings_trainer_profile_id_fkey
                FOREIGN KEY (trainer_profile_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                ALTER TABLE bookings ADD CONSTRAINT bookings_client_id_fkey
                FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE;

                ALTER TABLE bookings ADD CONSTRAINT bookings_slot_id_fkey
                FOREIGN KEY (slot_id) REFERENCES time_slots(id) ON DELETE CASCADE;

                ALTER TABLE reminders ADD CONSTRAINT reminders_booking_id_fkey
                FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE;

                ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_trainer_id_fkey
                FOREIGN KEY (trainer_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_client_id_fkey
                FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE;

                ALTER TABLE reviews ADD CONSTRAINT reviews_trainer_id_fkey
                FOREIGN KEY (trainer_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                ALTER TABLE reviews ADD CONSTRAINT reviews_client_id_fkey
                FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE;

                ALTER TABLE reviews ADD CONSTRAINT reviews_booking_id_fkey
                FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE;

            EXCEPTION WHEN others THEN
                RAISE NOTICE 'FK comprehensive repair error: %', SQLERRM;
            END $$;
            """
            await execute_sql_safe(engine, fk_script)

            # Columns addition
            await add_column_safe(engine, "bookings", "slot_id", "INTEGER")
            await add_column_safe(engine, "bookings", "client_id", "BIGINT")
            await add_column_safe(engine, "bookings", "start_time", "TIMESTAMP WITHOUT TIME ZONE")
            await add_column_safe(engine, "bookings", "end_time", "TIMESTAMP WITHOUT TIME ZONE")
            await add_column_safe(engine, "bookings", "status", "VARCHAR(50)")
            await add_column_safe(engine, "bookings", "price", "FLOAT")
            await add_column_safe(engine, "bookings", "paid", "BOOLEAN DEFAULT FALSE")
            await add_column_safe(engine, "bookings", "client_notes", "TEXT")
            await add_column_safe(engine, "bookings", "trainer_notes", "TEXT")
            await add_column_safe(engine, "bookings", "booked_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")

            await add_column_safe(engine, "client_profiles", "full_name", "VARCHAR(128)")
            await add_column_safe(engine, "client_profiles", "status", "VARCHAR(20) DEFAULT 'active'")

            await add_column_safe(engine, "reviews", "booking_id", "INTEGER")

            for col in ["google_client_id", "google_client_secret", "google_calendar_id"]:
                await add_column_safe(engine, "trainer_schedules", col, "VARCHAR(200)")
            for col in ["google_refresh_token", "google_access_token"]:
                await add_column_safe(engine, "trainer_schedules", col, "TEXT")
            await add_column_safe(engine, "trainer_schedules", "token_expires_at", "TIMESTAMP WITHOUT TIME ZONE")
            await add_column_safe(engine, "trainer_schedules", "sync_enabled", "BOOLEAN DEFAULT TRUE")
            await add_column_safe(engine, "trainer_schedules", "timezone", "VARCHAR(50) DEFAULT 'Europe/Moscow'")
            await add_column_safe(engine, "trainer_schedules", "slot_duration", "INTEGER DEFAULT 60")
            await add_column_safe(engine, "trainer_schedules", "rolling_window", "INTEGER")
            await add_column_safe(engine, "trainer_schedules", "last_replenished", "TIMESTAMP WITHOUT TIME ZONE")
            await add_column_safe(engine, "trainer_schedules", "updated_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")
            await add_column_safe(engine, "trainer_schedules", "wd_start", "INTEGER DEFAULT 7")
            await add_column_safe(engine, "trainer_schedules", "wd_end", "INTEGER DEFAULT 23")
            await add_column_safe(engine, "trainer_schedules", "we_start", "INTEGER DEFAULT 9")
            await add_column_safe(engine, "trainer_schedules", "we_end", "INTEGER DEFAULT 22")

            await add_column_safe(engine, "trainer_profiles", "price_single", "FLOAT DEFAULT 0.0")
            await add_column_safe(engine, "trainer_profiles", "price_online", "FLOAT DEFAULT 0.0")
            await add_column_safe(engine, "trainer_profiles", "price_package", "FLOAT DEFAULT 0.0")
            await add_column_safe(engine, "trainer_profiles", "service_prices", "JSON")
            await add_column_safe(engine, "trainer_profiles", "rating", "FLOAT DEFAULT 5.0")
            await add_column_safe(engine, "trainer_profiles", "is_premium", "BOOLEAN DEFAULT FALSE")
            await add_column_safe(engine, "trainer_profiles", "is_subscribed", "BOOLEAN DEFAULT FALSE")
            await add_column_safe(engine, "trainer_profiles", "subscription_expires_at", "TIMESTAMP WITHOUT TIME ZONE")
            await add_column_safe(engine, "trainer_profiles", "status", "VARCHAR(20) DEFAULT 'approved'")
            await add_column_safe(engine, "trainer_profiles", "district", "VARCHAR(100)")
            await add_column_safe(engine, "trainer_profiles", "phone", "VARCHAR(20)")
            await add_column_safe(engine, "trainer_profiles", "online_meeting_link", "VARCHAR(500)")

            await execute_sql_safe(engine, r"""
                UPDATE trainer_profiles
                SET phone = regexp_replace(phone, '\D', '', 'g')
                WHERE phone IS NOT NULL AND phone != '';
            """)

            await add_column_safe(engine, "time_slots", "format", "VARCHAR(100) DEFAULT 'hybrid'")
            await execute_sql_safe(engine, "ALTER TABLE time_slots ALTER COLUMN format TYPE VARCHAR(100)")

            await add_column_safe(engine, "time_slots", "google_event_id", "VARCHAR(200)")
            await add_column_safe(engine, "time_slots", "zoom_meeting_id", "VARCHAR(100)")
            await add_column_safe(engine, "time_slots", "zoom_join_url", "VARCHAR(500)")
            await add_column_safe(engine, "time_slots", "zoom_start_url", "VARCHAR(500)")
            await add_column_safe(engine, "time_slots", "online_platform", "VARCHAR(50)")
            await add_column_safe(engine, "time_slots", "max_clients", "INTEGER DEFAULT 1")
            await add_column_safe(engine, "time_slots", "notes", "TEXT")

            # Client data migration
            await execute_sql_safe(engine, """
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='client_profiles' AND column_name='id') THEN
                        ALTER TABLE client_profiles ADD COLUMN id SERIAL PRIMARY KEY;
                    END IF;
                END $$;
            """)
            await execute_sql_safe(engine, """
                INSERT INTO client_profiles (user_id, full_name, status)
                SELECT DISTINCT client_id, 'Клиент', 'active'
                FROM bookings WHERE client_id > 1000000
                ON CONFLICT (user_id) DO NOTHING
            """)
            await execute_sql_safe(engine, """
                UPDATE client_profiles cp SET full_name = u.full_name
                FROM users u WHERE cp.user_id = u.id
                AND (cp.full_name IS NULL OR cp.full_name = 'None' OR cp.full_name = 'Клиент')
            """)
            await execute_sql_safe(engine, """
                UPDATE bookings b SET client_id = cp.id
                FROM client_profiles cp WHERE b.client_id = cp.user_id AND b.client_id > 1000000;
            """)
            await execute_sql_safe(engine, "UPDATE bookings SET client_id = NULL WHERE client_id > 1000000")
            await execute_sql_safe(engine, "ALTER TABLE bookings ALTER COLUMN trainer_profile_id TYPE INTEGER USING trainer_profile_id::integer")
            await execute_sql_safe(engine, "ALTER TABLE bookings ALTER COLUMN client_id TYPE INTEGER USING client_id::integer")
            await execute_sql_safe(engine, "ALTER TABLE bookings ALTER COLUMN slot_id TYPE INTEGER USING slot_id::integer")

            await execute_sql_safe(engine, "ALTER TABLE bookings ALTER COLUMN is_online DROP NOT NULL")
            await execute_sql_safe(engine, """
                UPDATE bookings b SET
                    start_time = s.start_time,
                    end_time = s.end_time
                FROM time_slots s
                WHERE b.slot_id = s.id AND (b.start_time IS NULL OR b.end_time IS NULL)
            """)

        # Sync specializations
        await execute_sql_safe(engine, "ALTER TABLE specializations ALTER COLUMN name TYPE VARCHAR(100)")

        specs = [
            'Силовые тренировки', 'Похудение и жиросжигание', 'Функциональный тренинг',
            'Реабилитация и ОФП', 'Кроссфит / HIIT', 'Тренировки для женщин/мужчин',
            'Работа с подростками', 'Большой теннис', 'Падл', 'Маникюр', 'Педикюр',
            'Массаж', 'Косметология', 'Парикмахерские услуги', 'Брови и ресницы',
            'Макияж',
            'Индивидуальные тренировки', 'Групповые занятия', 'Тренировки для детей',
            'Подготовка к турнирам', 'Спарринг',
            'Другое'
        ]

        await execute_sql_safe(engine, "DELETE FROM specializations WHERE LENGTH(name) <= 1")

        count = 0
        for spec in specs:
            res = await execute_sql_safe(engine,
                "INSERT INTO specializations (name) VALUES (:name) ON CONFLICT (name) DO NOTHING",
                {"name": spec}
            )
            if res and res.rowcount > 0:
                count += 1
        logger.info(f"Specializations sync complete. Added {count} new entries.")

        print("✅ Все таблицы базы данных проверены/созданы и исправлены.")
    except Exception as e:
        print(f"⚠️ Ошибка при инициализации БД: {e}")

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def get_db():
    async with SessionLocal() as session:
        yield session
