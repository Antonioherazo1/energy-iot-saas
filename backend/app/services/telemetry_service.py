from datetime import datetime, timezone

from sqlalchemy import select
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
    }
    websocket_manager.broadcast_threadsafe("dashboard", payload)
    websocket_manager.broadcast_threadsafe(str(device.id), payload)


def create_telemetry(db: Session, device_code: str, payload: TelemetryIn) -> Telemetry | None:
    device = db.scalar(select(Device).where(Device.code == device_code, Device.is_active.is_(True)))
    if device is None:
        return None
    if not verify_device_key(payload.device_key, device.device_key_hash):
        raise InvalidDeviceKeyError

    now = datetime.now(timezone.utc)
    device.last_seen_at = now
    telemetry = Telemetry(
        device_id=device.id,
        recorded_at=payload.recorded_at or now,
        voltage=payload.voltage,
        current=payload.current,
        power=payload.power,
        energy_kwh=payload.energy_kwh,
        frequency=payload.frequency,
        power_factor=payload.power_factor,
    )
    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)
    publish_telemetry_event(device, telemetry)
    return telemetry
