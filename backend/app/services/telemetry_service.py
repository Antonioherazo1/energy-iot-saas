from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.channel import DeviceChannel
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
        "ch1_energy_kwh": decimal_to_string(telemetry.ch1_energy_kwh),
        "ch2_energy_kwh": decimal_to_string(telemetry.ch2_energy_kwh),
        "ch3_energy_kwh": decimal_to_string(telemetry.ch3_energy_kwh),
        "ch4_energy_kwh": decimal_to_string(telemetry.ch4_energy_kwh),
    }
    websocket_manager.broadcast_threadsafe("dashboard", payload)
    websocket_manager.broadcast_threadsafe(str(device.id), payload)


def _calc_channel_energy(
    prev: Telemetry | None,
    ch_power: Decimal,
    recorded_at: datetime,
    channel_number: int,
) -> Decimal:
    if ch_power is None or ch_power == 0:
        return Decimal("0")
    if prev is None:
        return Decimal("0")
    prev_energy = getattr(prev, f"ch{channel_number}_energy_kwh", None)
    if prev_energy is None:
        return Decimal("0")
    delta_hours = (recorded_at - prev.recorded_at).total_seconds() / 3600
    if delta_hours <= 0:
        return prev_energy
    increment = ch_power * Decimal(str(delta_hours)) / Decimal("1000")
    return prev_energy + increment


def create_telemetry(db: Session, device_code: str, payload: TelemetryIn) -> Telemetry | None:
    device = db.scalar(select(Device).where(Device.code == device_code, Device.is_active.is_(True)))
    if device is None:
        return None
    if not verify_device_key(payload.device_key, device.device_key_hash):
        raise InvalidDeviceKeyError

    now = datetime.now(timezone.utc)
    recorded_at = payload.recorded_at or now
    device.last_seen_at = now

    channels = list(db.scalars(
        select(DeviceChannel).where(
            DeviceChannel.device_id == device.id,
            DeviceChannel.is_active.is_(True),
        ).order_by(DeviceChannel.channel_number)
    ))

    prev = db.scalar(
        select(Telemetry)
        .where(Telemetry.device_id == device.id, Telemetry.recorded_at < recorded_at)
        .order_by(Telemetry.recorded_at.desc())
        .limit(1)
    )

    ch_currents = [payload.ch1, payload.ch2, payload.ch3, payload.ch4]
    ch_powers: list[Decimal | None] = [None, None, None, None]
    ch_energies: list[Decimal | None] = [None, None, None, None]
    total_power = Decimal("0")
    global_voltage = Decimal(str(settings.assumed_voltage))

    for idx in range(4):
        ch_current = ch_currents[idx]
        if ch_current is None:
            continue
        ch_config = next((c for c in channels if c.channel_number == idx + 1), None)
        ch_voltage = global_voltage if ch_config is None else ch_config.voltage
        ch_power_val = ch_current * ch_voltage
        ch_powers[idx] = ch_power_val
        total_power += ch_power_val
        ch_energies[idx] = _calc_channel_energy(prev, ch_power_val, recorded_at, idx + 1)

    total_current = sum(c for c in ch_currents if c is not None) or payload.current
    if total_current is None:
        total_current = Decimal("0")

    total_energy = sum(e for e in ch_energies if e is not None) or payload.energy_kwh

    telemetry = Telemetry(
        device_id=device.id,
        recorded_at=recorded_at,
        voltage=payload.voltage or global_voltage,
        current=total_current,
        power=total_power,
        energy_kwh=total_energy,
        frequency=payload.frequency,
        power_factor=payload.power_factor,
        ch1=payload.ch1,
        ch2=payload.ch2,
        ch3=payload.ch3,
        ch4=payload.ch4,
        ch1_energy_kwh=ch_energies[0],
        ch2_energy_kwh=ch_energies[1],
        ch3_energy_kwh=ch_energies[2],
        ch4_energy_kwh=ch_energies[3],
    )
    db.add(telemetry)
    db.commit()
    db.refresh(telemetry)
    publish_telemetry_event(device, telemetry)
    return telemetry
