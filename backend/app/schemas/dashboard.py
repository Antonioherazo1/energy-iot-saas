import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class DeviceStatusRead(BaseModel):
    device_id: uuid.UUID
    name: str
    code: str
    is_active: bool
    is_online: bool
    last_seen_at: datetime | None


class LatestTelemetryRead(BaseModel):
    device_id: uuid.UUID
    device_name: str
    device_code: str
    recorded_at: datetime | None
    voltage: Decimal | None
    current: Decimal | None
    power: Decimal | None
    energy_kwh: Decimal | None
    frequency: Decimal | None
    power_factor: Decimal | None
    ch1: Decimal | None
    ch2: Decimal | None
    ch3: Decimal | None
    ch4: Decimal | None


class EnergyBucketRead(BaseModel):
    period: date
    energy_kwh: Decimal


class DashboardSummaryRead(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    current_power: Decimal
    latest_energy_kwh: Decimal

