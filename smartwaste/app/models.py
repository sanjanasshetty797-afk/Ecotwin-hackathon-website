from datetime import datetime
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base, utcnow


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="viewer")  # admin | viewer


class Zone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    bins: Mapped[list["Bin"]] = relationship(back_populates="zone")


class Bin(Base):
    """Digital-twin node: the live virtual state of one physical bin."""
    __tablename__ = "bins"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    capacity_liters: Mapped[float] = mapped_column(Float, default=120.0)
    fill_level: Mapped[float] = mapped_column(Float, default=0.0)  # percent
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    device_key_hash: Mapped[str] = mapped_column(String(64), index=True)
    zone: Mapped[Zone] = relationship(back_populates="bins")


class BinReading(Base):
    """Time-series of fill levels (from ESP32 sensors or simulator)."""
    __tablename__ = "bin_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[int] = mapped_column(ForeignKey("bins.id", ondelete="CASCADE"))
    fill_level: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_reading_bin_time", "bin_id", "recorded_at"),)


class WasteClassification(Base):
    __tablename__ = "classifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[int | None] = mapped_column(ForeignKey("bins.id", ondelete="SET NULL"), nullable=True)
    label: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    scores: Mapped[dict] = mapped_column(JSON)
    image_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_class_bin_time", "bin_id", "created_at"),)


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    bin_id: Mapped[int] = mapped_column(ForeignKey("bins.id", ondelete="CASCADE"), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    collected_by: Mapped[str] = mapped_column(String(64))
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    level_before: Mapped[float] = mapped_column(Float)


class AIOutput(Base):
    """Stored GenAI recommendations & reports (audit + caching)."""
    __tablename__ = "ai_outputs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # recommendation | report
    bin_id: Mapped[int | None] = mapped_column(ForeignKey("bins.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32))  # claude | rule_based
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
