from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlalchemy import BigInteger, String, ForeignKey, Float, DateTime, Boolean, Table, Column, Enum as SQLEnum, Integer
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

class TrainerProfile(Base):
    __tablename__ = "trainer_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    city: Mapped[str] = mapped_column(String(100))
    experience: Mapped[str] = mapped_column(String(500))
    certificates: Mapped[Optional[str]] = mapped_column(String(1000))
    work_format: Mapped[WorkFormat] = mapped_column(SQLEnum(WorkFormat))
    price_per_session: Mapped[float] = mapped_column(Float)
    photo_url: Mapped[Optional[str]] = mapped_column(String(512))
    video_presentation_url: Mapped[Optional[str]] = mapped_column(String(512))
    rating: Mapped[float] = mapped_column(Float, default=5.0)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="trainer_profile")
    specializations: Mapped[List[Specialization]] = relationship(
        secondary=trainer_specializations, backref="trainers"
    )
    bookings: Mapped[List["Booking"]] = relationship(back_populates="trainer")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="trainer")

class ClientProfile(Base):
    __tablename__ = "client_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    city: Mapped[Optional[str]] = mapped_column(String(100))

    user: Mapped["User"] = relationship(back_populates="client_profile")
    bookings: Mapped[List["Booking"]] = relationship(back_populates="client")
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="client")

class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainer_profiles.id"))
    client_id: Mapped[int] = mapped_column(ForeignKey("client_profiles.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending, confirmed, cancelled, completed
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)

    trainer: Mapped["TrainerProfile"] = relationship(back_populates="bookings")
    client: Mapped["ClientProfile"] = relationship(back_populates="bookings")

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
