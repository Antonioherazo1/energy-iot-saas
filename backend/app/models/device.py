import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class Device(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_device_org_code"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    mqtt_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    device_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    telemetry: Mapped[list["Telemetry"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    channels: Mapped[list["DeviceChannel"]] = relationship(back_populates="device", cascade="all, delete-orphan")
