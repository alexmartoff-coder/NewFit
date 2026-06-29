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
        # 0. PostgreSQL absolute first fixes
        if "postgresql" in str(engine.url).lower():
            async with engine.connect() as conn:
                try:
                    # Fix column length for specializations.name before anything else
                    await conn.execute(text("ALTER TABLE specializations ALTER COLUMN name TYPE VARCHAR(100)"))
                    await conn.commit()
                except Exception:
                    await conn.rollback()

        # 1. Применяем переименования таблиц и колонок ДО создания через Base.metadata.create_all
        if "postgresql" in str(engine.url).lower():
            async with engine.connect() as conn:
                # Переименовываем professional_ обратно в trainer_, если они вдруг есть
                tables_to_rename = [
                    ("professional_profiles", "trainer_profiles"),
                    ("professional_schedules", "trainer_schedules"),
                    ("professional_templates", "schedule_templates"),
                    ("professional_specializations", "trainer_specializations")
                ]
                for old_name, new_name in tables_to_rename:
                    try:
                        res = await conn.execute(text(f"SELECT 1 FROM pg_tables WHERE tablename = '{old_name}'"))
                        if res.scalar():
                            res_new = await conn.execute(text(f"SELECT 1 FROM pg_tables WHERE tablename = '{new_name}'"))
                            if not res_new.scalar():
                                logger.info(f"Renaming table {old_name} back to {new_name}")
                                await conn.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                                await conn.commit()
                    except Exception as e:
                        logger.warning(f"Could not rename table {old_name}: {e}")
                        await conn.rollback()

                # Колонки
                columns_to_rename = [
                    ("time_slots", "professional_profile_id", "trainer_profile_id"),
                    ("bookings", "professional_profile_id", "trainer_profile_id"),
                    ("trainer_schedules", "professional_id", "trainer_id"),
                    ("schedule_templates", "professional_id", "trainer_id")
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
                                # Both exist? Merge and drop old
                                logger.info(f"Both {old_col} and {new_col} exist in {table}. Dropping old {old_col} to avoid conflicts.")
                                await conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {old_col} DROP NOT NULL"))
                                try:
                                    await conn.execute(text(f"UPDATE {table} SET {new_col} = {old_col} WHERE {new_col} IS NULL"))
                                except Exception: pass
                                await conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {old_col}"))
                                await conn.commit()
                    except Exception as e:
                        logger.warning(f"Could not process column rename/merge for {table}.{old_col}: {e}")
                        await conn.rollback()

        # Fix for SQLite
        if "sqlite" in str(engine.url).lower():
            async with engine.connect() as conn:
                try:
                    res = await conn.execute(text("PRAGMA table_info('time_slots')"))
                    cols = [c[1] for c in res.fetchall()]
                    if "professional_profile_id" in cols and "trainer_profile_id" not in cols:
                        logger.info("Renaming professional_profile_id to trainer_profile_id in SQLite")
                        await conn.execute(text("ALTER TABLE time_slots RENAME COLUMN professional_profile_id TO trainer_profile_id"))
                        await conn.commit()
                    elif "professional_profile_id" in cols and "trainer_profile_id" in cols:
                        await conn.execute(text("ALTER TABLE time_slots DROP COLUMN professional_profile_id"))
                        await conn.commit()
                except Exception as e:
                    logger.warning(f"SQLite migration error: {e}")
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
                    await conn.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'TENNIS'"))
                    await conn.execute(text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'PADEL'"))
                    await conn.commit()
                except Exception as e:
                    await conn.rollback()
                    logger.warning(f"Could not add roles to userrole enum: {e}")

                # Вспомогательная функция для добавления колонки
                async def add_column_safe(table, col_name, col_type):
                    try:
                        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                        await conn.commit()
                    except Exception as e:
                        logger.error(f"Error adding {col_name} to {table}: {e}")
                        await conn.rollback()

                # Обеспечиваем наличие критических колонок
                try:
                    await conn.execute(text("ALTER TABLE specializations ALTER COLUMN name TYPE VARCHAR(100)"))
                    await conn.commit()
                except Exception:
                    await conn.rollback()

                await add_column_safe("time_slots", "trainer_profile_id", "INTEGER")
                await add_column_safe("bookings", "trainer_profile_id", "INTEGER")
                await add_column_safe("trainer_schedules", "trainer_id", "BIGINT")
                await add_column_safe("schedule_templates", "trainer_id", "BIGINT")

                # Ensure unique constraints for ON CONFLICT before migration
                try:
                    # Clear duplicates and recreate constraint for specializations
                    await conn.execute(text("""
                        DELETE FROM specializations WHERE id NOT IN (
                            SELECT MIN(id) FROM specializations GROUP BY name
                        )
                    """))
                    await conn.execute(text("ALTER TABLE specializations DROP CONSTRAINT IF EXISTS specializations_name_key"))
                    await conn.execute(text("ALTER TABLE specializations ADD CONSTRAINT specializations_name_key UNIQUE (name)"))
                    await conn.commit()
                except Exception as e:
                    logger.warning(f"Could not fix specialization unique constraint: {e}")
                    await conn.rollback()

                try:
                    # Clear duplicates and recreate constraint for client_profiles
                    await conn.execute(text("""
                        DELETE FROM client_profiles WHERE id NOT IN (
                            SELECT MIN(id) FROM client_profiles GROUP BY user_id
                        )
                    """))
                    await conn.execute(text("ALTER TABLE client_profiles DROP CONSTRAINT IF EXISTS client_profiles_user_id_key"))
                    await conn.execute(text("ALTER TABLE client_profiles ADD CONSTRAINT client_profiles_user_id_key UNIQUE (user_id)"))
                    await conn.commit()
                except Exception as e:
                    logger.warning(f"Could not fix client_profile unique constraint: {e}")
                    await conn.rollback()

                # Comprehensive Foreign Key Repair with CASCADE
                fk_script = """
                DO $$
                DECLARE
                    r RECORD;
                BEGIN
                    -- 1. Drop ALL existing foreign keys to avoid conflicts and outdated constraints
                    FOR r IN (SELECT constraint_name, table_name
                              FROM information_schema.table_constraints
                              WHERE constraint_type = 'FOREIGN KEY'
                              AND table_schema = 'public')
                    LOOP
                        EXECUTE 'ALTER TABLE public.' || quote_ident(r.table_name) || ' DROP CONSTRAINT ' || quote_ident(r.constraint_name);
                    END LOOP;

                    -- 2. Recreate constraints with ON DELETE CASCADE for all relationships

                    -- User Profiles
                    ALTER TABLE trainer_profiles ADD CONSTRAINT trainer_profiles_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

                    ALTER TABLE client_profiles ADD CONSTRAINT client_profiles_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

                    -- Schedule & Templates
                    ALTER TABLE trainer_schedules ADD CONSTRAINT trainer_schedules_trainer_id_fkey
                    FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE;

                    ALTER TABLE schedule_templates ADD CONSTRAINT schedule_templates_trainer_id_fkey
                    FOREIGN KEY (trainer_id) REFERENCES users(id) ON DELETE CASCADE;

                    -- Specializations (Many-to-Many)
                    ALTER TABLE trainer_specializations ADD CONSTRAINT trainer_specializations_trainer_id_fkey
                    FOREIGN KEY (trainer_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                    ALTER TABLE trainer_specializations ADD CONSTRAINT trainer_specializations_spec_id_fkey
                    FOREIGN KEY (specialization_id) REFERENCES specializations(id) ON DELETE CASCADE;

                    -- Time Slots
                    ALTER TABLE time_slots ADD CONSTRAINT time_slots_trainer_profile_id_fkey
                    FOREIGN KEY (trainer_profile_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                    -- Bookings
                    ALTER TABLE bookings ADD CONSTRAINT bookings_trainer_profile_id_fkey
                    FOREIGN KEY (trainer_profile_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                    ALTER TABLE bookings ADD CONSTRAINT bookings_client_id_fkey
                    FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE;

                    ALTER TABLE bookings ADD CONSTRAINT bookings_slot_id_fkey
                    FOREIGN KEY (slot_id) REFERENCES time_slots(id) ON DELETE CASCADE;

                    -- Reminders
                    ALTER TABLE reminders ADD CONSTRAINT reminders_booking_id_fkey
                    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE;

                    -- Subscriptions
                    ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_trainer_id_fkey
                    FOREIGN KEY (trainer_id) REFERENCES trainer_profiles(id) ON DELETE CASCADE;

                    ALTER TABLE subscriptions ADD CONSTRAINT subscriptions_client_id_fkey
                    FOREIGN KEY (client_id) REFERENCES client_profiles(id) ON DELETE CASCADE;

                    -- Reviews
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
                await add_column_safe("bookings", "trainer_notes", "TEXT")
                await add_column_safe("bookings", "booked_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")

                await add_column_safe("client_profiles", "full_name", "VARCHAR(128)")
                await add_column_safe("client_profiles", "status", "VARCHAR(20) DEFAULT 'active'")

                await add_column_safe("reviews", "booking_id", "INTEGER")


                # trainer_schedules columns
                for col in ["google_client_id", "google_client_secret", "google_calendar_id"]:
                    await add_column_safe("trainer_schedules", col, "VARCHAR(200)")
                for col in ["google_refresh_token", "google_access_token"]:
                    await add_column_safe("trainer_schedules", col, "TEXT")
                await add_column_safe("trainer_schedules", "token_expires_at", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("trainer_schedules", "sync_enabled", "BOOLEAN DEFAULT TRUE")
                await add_column_safe("trainer_schedules", "timezone", "VARCHAR(50) DEFAULT 'Europe/Moscow'")
                await add_column_safe("trainer_schedules", "slot_duration", "INTEGER DEFAULT 60")
                await add_column_safe("trainer_schedules", "rolling_window", "INTEGER")
                await add_column_safe("trainer_schedules", "last_replenished", "TIMESTAMP WITHOUT TIME ZONE")
                await add_column_safe("trainer_schedules", "updated_at", "TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()")

                # trainer_profiles columns
                await add_column_safe("trainer_profiles", "price_single", "FLOAT DEFAULT 0.0")
                await add_column_safe("trainer_profiles", "price_online", "FLOAT DEFAULT 0.0")
                await add_column_safe("trainer_profiles", "price_package", "FLOAT DEFAULT 0.0")
                await add_column_safe("trainer_profiles", "service_prices", "JSON")
                await add_column_safe("trainer_profiles", "rating", "FLOAT DEFAULT 5.0")
                await add_column_safe("trainer_profiles", "is_premium", "BOOLEAN DEFAULT FALSE")
                await add_column_safe("trainer_profiles", "status", "VARCHAR(20) DEFAULT 'approved'")
                await add_column_safe("trainer_profiles", "district", "VARCHAR(100)")
                await add_column_safe("trainer_profiles", "phone", "VARCHAR(20)")
                await add_column_safe("trainer_profiles", "online_meeting_link", "VARCHAR(500)")

                # Normalize existing phone numbers in trainer_profiles
                try:
                    await conn.execute(text("""
                        UPDATE trainer_profiles
                        SET phone = regexp_replace(phone, '\D', '', 'g')
                        WHERE phone IS NOT NULL AND phone != '';
                    """))
                    await conn.commit()
                except Exception as e:
                    logger.warning(f"Could not normalize phone numbers: {e}")
                    await conn.rollback()

                # time_slots extra
                await add_column_safe("time_slots", "format", "VARCHAR(100) DEFAULT 'hybrid'")
                try:
                    await conn.execute(text("ALTER TABLE time_slots ALTER COLUMN format TYPE VARCHAR(100)"))
                    await conn.commit()
                except Exception: await conn.rollback()

                await add_column_safe("time_slots", "google_event_id", "VARCHAR(200)")
                await add_column_safe("time_slots", "zoom_meeting_id", "VARCHAR(100)")
                await add_column_safe("time_slots", "zoom_join_url", "VARCHAR(500)")
                await add_column_safe("time_slots", "zoom_start_url", "VARCHAR(500)")
                await add_column_safe("time_slots", "online_platform", "VARCHAR(50)")
                await add_column_safe("time_slots", "max_clients", "INTEGER DEFAULT 1")
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
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN trainer_profile_id TYPE INTEGER USING trainer_profile_id::integer"))
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN client_id TYPE INTEGER USING client_id::integer"))
                    await conn.execute(text("ALTER TABLE bookings ALTER COLUMN slot_id TYPE INTEGER USING slot_id::integer"))

                    try:
                        await conn.execute(text("ALTER TABLE bookings ALTER COLUMN is_online DROP NOT NULL"))
                    except Exception: pass

                    await conn.commit()
                except Exception as e:
                    logger.error(f"Data migration error: {e}")
                    await conn.rollback()

        async with engine.connect() as conn:
            # Fix column length for specializations.name
            try:
                await conn.execute(text("ALTER TABLE specializations ALTER COLUMN name TYPE VARCHAR(100)"))
                await conn.commit()
            except Exception:
                await conn.rollback()

            # Добавляем список специализаций
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

            # Clear potentially truncated entries if they exist (names with length 1 or non-cyrillic artifacts)
            try:
                # Character length of 1 or very short names are likely corrupted
                await conn.execute(text("DELETE FROM specializations WHERE LENGTH(name) <= 1"))
                await conn.commit()
            except Exception:
                await conn.rollback()

            count = 0
            for spec in specs:
                res = await conn.execute(
                    text("INSERT INTO specializations (name) VALUES (:name) ON CONFLICT (name) DO NOTHING"),
                    {"name": spec}
                )
                if res.rowcount > 0:
                    count += 1
            await conn.commit()
            logger.info(f"Specializations sync complete. Added {count} new entries.")
        print("✅ Все таблицы базы данных проверены/созданы и исправлены.")
    except Exception as e:
        print(f"⚠️ Ошибка при инициализации БД: {e}")

SessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

async def get_db():
    async with SessionLocal() as session:
        yield session
