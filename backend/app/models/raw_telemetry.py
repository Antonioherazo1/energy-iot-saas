import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RawTelemetry(Base):
    __tablename__ = "raw_telemetry"
    __table_args__ = (
        Index("ix_raw_telemetry_device_recorded_at", "device_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ch1: Mapped[float | None] = mapped_column(Float, nullable=True)
    ch2: Mapped[float | None] = mapped_column(Float, nullable=True)
    ch3: Mapped[float | None] = mapped_column(Float, nullable=True)
    ch4: Mapped[float | None] = mapped_column(Float, nullable=True)
    energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    voltage: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    ch1_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ch2_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ch3_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ch4_energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
