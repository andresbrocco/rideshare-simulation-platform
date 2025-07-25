"""SQLAlchemy ORM models for simulation persistence."""

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .utils import utc_now


class Base(DeclarativeBase):
    pass


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dna_json: Mapped[str] = mapped_column(Text, nullable=False)
    current_location: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    active_trip: Mapped[str | None] = mapped_column(String, nullable=True)
    current_rating: Mapped[float] = mapped_column(Float, default=5.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=lambda: utc_now())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
    )

    __table_args__ = (Index("idx_driver_status", "status"),)


class Rider(Base):
    __tablename__ = "riders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dna_json: Mapped[str] = mapped_column(Text, nullable=False)
    current_location: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    active_trip: Mapped[str | None] = mapped_column(String, nullable=True)
    current_rating: Mapped[float] = mapped_column(Float, default=5.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=lambda: utc_now())
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
    )

    __table_args__ = (Index("idx_rider_status", "status"),)


class Trip(Base):
    __tablename__ = "trips"

    trip_id: Mapped[str] = mapped_column(String, primary_key=True)
    rider_id: Mapped[str] = mapped_column(String, nullable=False)
    driver_id: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    pickup_location: Mapped[str] = mapped_column(String, nullable=False)
    dropoff_location: Mapped[str] = mapped_column(String, nullable=False)
    pickup_zone_id: Mapped[str] = mapped_column(String, nullable=False)
    dropoff_zone_id: Mapped[str] = mapped_column(String, nullable=False)
    surge_multiplier: Mapped[float] = mapped_column(Float, nullable=False)
    fare: Mapped[float] = mapped_column(Float, nullable=False)
    offer_sequence: Mapped[int] = mapped_column(Integer, default=0)
    cancelled_by: Mapped[str | None] = mapped_column(String, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    cancellation_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(nullable=True)
    matched_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
    )

    __table_args__ = (
        Index("idx_trip_state", "state"),
        Index("idx_trip_driver", "driver_id"),
        Index("idx_trip_rider", "rider_id"),
    )


class SimulationMetadata(Base):
    __tablename__ = "simulation_metadata"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
    )


class RouteCache(Base):
    __tablename__ = "route_cache"

    cache_key: Mapped[str] = mapped_column(String, primary_key=True)
    origin_h3: Mapped[str] = mapped_column(String, nullable=False)
    dest_h3: Mapped[str] = mapped_column(String, nullable=False)
    distance: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: utc_now())

    __table_args__ = (Index("idx_route_cache_created", "created_at"),)
