from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy import BigInteger, String, ForeignKey, Float, DateTime, Boolean, Table, Column, Enum as SQLEnum, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class UserRole(str, Enum):
    TRAINER = "trainer"
    CLIENT = "client"
    ADMIN = "admin"

class WorkFormat(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    HYBRID = "hybrid"

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
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trainer_profile: Mapped["TrainerProfile"] = relationship(back_populates="user", cascade="all, delete-orphan")
    client_profile: Mapped["ClientProfile"] = relationship(back_populates="user", cascade="all, delete-orphan")

    admins = relationship("Admin", foreign_keys="Admin.user_id")
    schedule = relationship("TrainerSchedule", back_populates="trainer", uselist=False)
    time_slots = relationship("TimeSlot", foreign_keys="TimeSlot.trainer_id")
    bookings_as_trainer = relationship("Booking", foreign_keys="Booking.trainer_id")
    bookings_as_client = relationship("Booking", foreign_keys="Booking.client_id")

class TrainerProfile(Base):
    __tablename__ = "trainer_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    city: Mapped[str] = mapped_column(String(100))
    experience: Mapped[str] = mapped_column(String(500))
    certificates: Mapped[Optional[str]] = mapped_column(String(1000))
    work_format: Mapped[WorkFormat] = mapped_column(SQLEnum(WorkFormat))
    price_single: Mapped[float] = mapped_column(Float, default=0.0)
    price_package: Mapped[float] = mapped_column(Float, default=0.0)
    photo_url: Mapped[Optional[str]] = mapped_column(String(512))
    video_presentation_url: Mapped[Optional[str]] = mapped_column(String(512))
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="trainer_profile")
    specializations: Mapped[List[Specialization]] = relationship(
        secondary=trainer_specializations, backref="trainers"
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="trainer")

class ClientProfile(Base):
    __tablename__ = "client_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    city: Mapped[Optional[str]] = mapped_column(String(100))

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
    trainer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    google_calendar_id = Column(String(200), nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    sync_enabled = Column(Boolean, default=True)
    timezone = Column(String(50), default="Europe/Moscow")
    slot_duration = Column(Integer, default=60)
    break_between_slots = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    trainer = relationship("User", back_populates="schedule")


class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True)
    trainer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    client_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(50), default="free")  # free, booked, canceled, completed
    google_event_id = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    slot_id = Column(Integer, ForeignKey("time_slots.id"), unique=True)
    trainer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    client_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, confirmed, canceled, completed
    price = Column(Integer, nullable=True)
    paid = Column(Boolean, default=False)
    client_notes = Column(Text, nullable=True)
    trainer_notes = Column(Text, nullable=True)
    booked_at = Column(DateTime, default=datetime.utcnow)
