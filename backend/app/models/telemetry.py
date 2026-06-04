import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        Index("ix_telemetry_device_recorded_at", "device_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, default=lambda: datetime.now(timezone.utc), nullable=False)
    voltage: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    current: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    power: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    energy_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    frequency: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    power_factor: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    ch1: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    ch2: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    ch3: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    ch4: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)

    device: Mapped["Device"] = relationship(back_populates="telemetry")
