from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryIn
from app.services.device_credentials import verify_device_key
from app.websockets.manager import websocket_manager


class InvalidDeviceKeyError(Exception):
    pass


def decimal_to_string(value):
    return str(value) if value is not None else None


def publish_telemetry_event(device: Device, telemetry: Telemetry) -> None:
    payload = {
        "type": "telemetry.created",
        "device_id": str(device.id),
        "device_code": device.code,
        "organization_id": str(device.organization_id),
        "recorded_at": telemetry.recorded_at.isoformat(),
        "voltage": decimal_to_string(telemetry.voltage),
        "current": decimal_to_string(telemetry.current),
        "power": decimal_to_string(telemetry.power),
        "energy_kwh": decimal_to_string(telemetry.energy_kwh),
        "frequency": decimal_to_string(telemetry.frequency),
        "power_factor": decimal_to_string(telemetry.power_factor),
        "ch1": decimal_to_string(telemetry.ch1),
        "ch2": decimal_to_string(telemetry.ch2),
        "ch3": decimal_to_string(telemetry.ch3),
        "ch4": decimal_to_string(telemetry.ch4),
    }
    websocket_manager.broadcast_threadsafe("dashboard", payload)
    websocket_manager.broadcast_threadsafe(str(device.id), payload)


def calculate_energy_kwh(db: Session, device_id, recorded_at, power) -> Decimal | None:
    if power is None:
        return None
    prev = db.scalar(
        select(Telemetry)
        .where(Telemetry.device_id == device_id, Telemetry.recorded_at < recorded_at)
        .order_by(Telemetry.recorded_at.desc())
        .limit(1)
    )
    if prev is None or prev.energy_kwh is None:
        return Decimal("0")
    delta_hours = (recorded_at - prev.recorded_at).total_seconds() / 3600
    if delta_hours <= 0:
        return prev.energy_kwh
    increment = Decimal(str(power)) * Decimal(str(delta_hours)) / Decimal("1000")
    return prev.energy_kwh + increment


def create_telemetry(db: Session, device_code: str, payload: TelemetryIn) -> Telemetry | None:
    device = db.scalar(select(Device).where(Device.code == device_code, Device.is_active.is_(True)))
    if device is None:
        return None
    if not verify_device_key(payload.device_key, device.device_key_hash):
        raise InvalidDeviceKeyError

    now = datetime.now(timezone.utc)
    recorded_at = payload.recorded_at or now
    device.last_seen_at = now
    energy_kwh = payload.energy_kwh or calculate_energy_kwh(db, device.id, recorded_at, payload.power)
    print(f"[TELEMETRY] ch1={payload.ch1} ch2={payload.ch2} ch3={payload.ch3} ch4={payload.ch4} power={payload.power}", flush=True)
    telemetry = Telemetry(
        device_id=device.id,
        recorded_at=recorded_at,
        voltage=payload.voltage,
        current=payload.current,
        power=payload.power,
        energy_kwh=energy_kwh,
        frequency=payload.frequency,
        power_factor=payload.power_factor,
        ch1=payload.ch1,
        ch2=payload.ch2,
        ch3=payload.ch3,
        ch4=payload.ch4,
    )
    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)
    publish_telemetry_event(device, telemetry)
    return telemetry
