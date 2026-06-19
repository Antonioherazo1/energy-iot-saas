import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class TelemetryBase(BaseModel):
    voltage: Decimal | None = None
    energy_kwh: Decimal | None = None
    frequency: Decimal | None = None
    power_factor: Decimal | None = None
    ch1: Decimal | None = None
    ch2: Decimal | None = None
    ch3: Decimal | None = None
    ch4: Decimal | None = None
    recorded_at: datetime | None = None


class TelemetryIn(TelemetryBase):
    device_key: str | None = None


class TelemetryRead(TelemetryBase):
    id: uuid.UUID
    device_id: uuid.UUID
    recorded_at: datetime

    model_config = {"from_attributes": True}
