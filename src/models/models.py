from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy import BigInteger, String, ForeignKey, Float, DateTime, Boolean, Table, Column, Enum as SQLEnum, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class UserRole(str, Enum):
    TRAINER = "TRAINER"
    CLIENT = "CLIENT"
    ADMIN = "ADMIN"
    BEAUTY = "BEAUTY"

class WorkFormat(str, Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    HYBRID = "HYBRID"

# Association table for trainer and specializations
trainer_specializations = Table(
    "trainer_specializations",
    Base.metadata,
    Column("trainer_id", ForeignKey("trainer_profiles.id"), primary_key=True),
    Column("specialization_id", ForeignKey("specializations.id"), primary_key=True),
)

class Specialization(Base):
    __tablename__ = "specializations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # Telegram ID
    username: Mapped[Optional[str]] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=True)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trainer_profile: Mapped["TrainerProfile"] = relationship(back_populates="user", cascade="all, delete-orphan")
    client_profile: Mapped["ClientProfile"] = relationship(back_populates="user", cascade="all, delete-orphan")

    admins = relationship("Admin", foreign_keys="Admin.user_id")
    schedule = relationship("TrainerSchedule", back_populates="trainer", uselist=False)
    time_slots = relationship("TimeSlot", foreign_keys="TimeSlot.client_id")

class TrainerProfile(Base):
    __tablename__ = "trainer_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)
    city: Mapped[str] = mapped_column(String(100))
    experience: Mapped[int] = mapped_column(Integer, default=0)
    certificates: Mapped[Optional[str]] = mapped_column(String(1000))
    work_format: Mapped[WorkFormat] = mapped_column(SQLEnum(WorkFormat))
    price_single: Mapped[float] = mapped_column(Float, default=0.0)
    price_package: Mapped[float] = mapped_column(Float, default=0.0)
    photo_url: Mapped[Optional[str]] = mapped_column(String(512))
    video_presentation_url: Mapped[Optional[str]] = mapped_column(String(512))
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="approved") # pending, approved, rejected

    user: Mapped["User"] = relationship(back_populates="trainer_profile")
    specializations: Mapped[List[Specialization]] = relationship(
        secondary=trainer_specializations, backref="trainers"
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="trainer")
    bookings: Mapped[List["Booking"]] = relationship(back_populates="trainer_profile")

class ClientProfile(Base):
    __tablename__ = "client_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), unique=True)
    full_name: Mapped[str] = mapped_column(String(128), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")

    user: Mapped["User"] = relationship(back_populates="client_profile")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="client")

class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainer_profiles.id"))
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.id"))
    total_sessions: Mapped[int] = mapped_column(Integer)
    remaining_sessions: Mapped[int] = mapped_column(Integer)
    purchase_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    trainer: Mapped["TrainerProfile"] = relationship(back_populates="subscriptions")
    client: Mapped["ClientProfile"] = relationship(back_populates="subscriptions")

class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainer_profiles.id"))
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# ========== АДМИН-ПАНЕЛЬ ==========

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False)
    role = Column(String(50), default="admin")  # "owner", "co_admin", "tester_trainer", "tester_client", "tester_both"
    added_by = Column(BigInteger, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    can_test_trainer = Column(Boolean, default=False)
    can_test_client = Column(Boolean, default=False)


# ========== КАЛЕНДАРЬ И РАСПИСАНИЕ ==========

class TrainerSchedule(Base):
    __tablename__ = "trainer_schedules"

    id = Column(Integer, primary_key=True)
    trainer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True)
    google_client_id = Column(String(200), nullable=True)
    google_client_secret = Column(String(200), nullable=True)
    google_calendar_id = Column(String(200), nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_access_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    sync_enabled = Column(Boolean, default=True)
    timezone = Column(String(50), default="Europe/Moscow")
    slot_duration = Column(Integer, default=60)
    rolling_window = Column(Integer, nullable=True) # In days: 7, 14, 30
    last_replenished = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trainer = relationship("User", back_populates="schedule")


class ScheduleTemplate(Base):
    """Шаблоны повторяющегося расписания"""
    __tablename__ = "schedule_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    trainer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    day_of_week: Mapped[int] = mapped_column(Integer) # 0-6 (Mon-Sun)
    start_time: Mapped[str] = mapped_column(String(5)) # HH:MM
    end_time: Mapped[str] = mapped_column(String(5)) # HH:MM
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


from sqlalchemy import func, Numeric

class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True)
    booking: Mapped["Booking"] = relationship(back_populates="slot", uselist=False)
    trainer_profile_id = Column(Integer, ForeignKey("trainer_profiles.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(20), default="free")
    format = Column(String(20), default="hybrid")
    price = Column(Float, nullable=False, default=0.0)
    google_event_id = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    trainer_profile = relationship("TrainerProfile", backref="time_slots")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("time_slots.id"), unique=True)
    slot: Mapped["TimeSlot"] = relationship(back_populates="booking")
    trainer_profile_id = Column(Integer, ForeignKey("trainer_profiles.id"), nullable=False)
    trainer_profile: Mapped["TrainerProfile"] = relationship(back_populates="bookings")
    client_id = Column(Integer, ForeignKey("client_profiles.id"), nullable=False)
    client: Mapped["ClientProfile"] = relationship()
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(50), default="pending")  # pending, confirmed, canceled, completed
    price = Column(Float, nullable=True)
    paid = Column(Boolean, default=False)
    client_notes = Column(Text, nullable=True)
    trainer_notes = Column(Text, nullable=True)
    booked_at = Column(DateTime, default=datetime.utcnow)

class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    reminder_type: Mapped[str] = mapped_column(String(20)) # "24h", "2h"
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending, sent, canceled
