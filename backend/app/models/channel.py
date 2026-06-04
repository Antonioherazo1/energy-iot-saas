import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.common import TimestampMixin, UUIDPrimaryKeyMixin


class DeviceChannel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "device_channels"
    __table_args__ = (
        UniqueConstraint("device_id", "channel_number", name="uq_device_channel"),
    )

    device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    voltage: Mapped[Decimal] = mapped_column(Numeric(6, 1), nullable=False, default=110)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    device: Mapped["Device"] = relationship(back_populates="channels")
