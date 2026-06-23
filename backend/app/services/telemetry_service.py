from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.channel import DeviceChannel
from app.models.device import Device
from app.models.raw_telemetry import RawTelemetry
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
    prev_energy: Decimal | None,
    ch_power: Decimal,
    delta_hours: float,
) -> Decimal:
    if prev_energy is None or ch_power is None or ch_power == 0:
        return prev_energy or Decimal("0")
    if delta_hours <= 0:
        return prev_energy
    increment = ch_power * Decimal(str(delta_hours)) / Decimal("1000")
    return prev_energy + increment


def _get_prev_energy_record(db: Session, device_id, recorded_at):
    """Find the most recent energy record before recorded_at, checking raw first then aggregated."""
    prev_raw = db.scalar(
        select(RawTelemetry)
        .where(RawTelemetry.device_id == device_id, RawTelemetry.recorded_at < recorded_at)
        .order_by(RawTelemetry.recorded_at.desc())
        .limit(1)
    )
    prev_agg = db.scalar(
        select(Telemetry)
        .where(Telemetry.device_id == device_id, Telemetry.recorded_at < recorded_at)
        .order_by(Telemetry.recorded_at.desc())
        .limit(1)
    )
    if prev_raw and prev_agg:
        return prev_raw if prev_raw.recorded_at > prev_agg.recorded_at else prev_agg
    return prev_raw or prev_agg


def store_raw_telemetry(db: Session, device_code: str, payload: TelemetryIn) -> RawTelemetry | None:
    device = db.scalar(select(Device).where(Device.code == device_code, Device.is_active.is_(True)))
    if device is None:
        return None
    if not verify_device_key(payload.device_key, device.device_key_hash):
        raise InvalidDeviceKeyError

    now = datetime.now(timezone.utc)
    recorded_at = payload.recorded_at or now
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    device.last_seen_at = now

    channels = list(db.scalars(
        select(DeviceChannel).where(
            DeviceChannel.device_id == device.id,
            DeviceChannel.is_active.is_(True),
        ).order_by(DeviceChannel.channel_number)
    ))

    prev = _get_prev_energy_record(db, device.id, recorded_at)
    delta_hours = (recorded_at - prev.recorded_at).total_seconds() / 3600 if prev else 0

    ch_currents = [payload.ch1, payload.ch2, payload.ch3, payload.ch4]
    ch_energies: list[Decimal | None] = [None, None, None, None]
    global_voltage = Decimal(str(settings.assumed_voltage))
    has_channels = len(channels) > 0

    for idx in range(4):
        ch_current = ch_currents[idx]
        if ch_current is None:
            continue
        ch_config = next((c for c in channels if c.channel_number == idx + 1), None)
        if has_channels and ch_config is None:
            continue
        ch_voltage = global_voltage if ch_config is None else ch_config.voltage
        ch_power_val = Decimal(str(float(ch_current) * float(ch_voltage)))
        prev_ch_energy = getattr(prev, f"ch{idx + 1}_energy_kwh", None) if prev else None
        ch_energies[idx] = _calc_channel_energy(prev_ch_energy, ch_power_val, delta_hours if prev else 0)

    total_energy = sum(e for e in ch_energies if e is not None) or payload.energy_kwh

    raw = RawTelemetry(
        device_id=device.id,
        recorded_at=recorded_at,
        voltage=float(payload.voltage or global_voltage),
        energy_kwh=total_energy,
        frequency=float(payload.frequency) if payload.frequency else None,
        power_factor=float(payload.power_factor) if payload.power_factor else None,
        ch1=float(payload.ch1) if payload.ch1 else None,
        ch2=float(payload.ch2) if payload.ch2 else None,
        ch3=float(payload.ch3) if payload.ch3 else None,
        ch4=float(payload.ch4) if payload.ch4 else None,
        ch1_energy_kwh=ch_energies[0],
        ch2_energy_kwh=ch_energies[1],
        ch3_energy_kwh=ch_energies[2],
        ch4_energy_kwh=ch_energies[3],
    )
    db.add(raw)
    db.commit()
    db.refresh(raw)
    publish_telemetry_event(device, raw)
    return raw


def aggregate_raw_telemetry(db: Session) -> int:
    """Aggregate raw readings from the last complete minute into telemetry."""
    now = datetime.now(timezone.utc)
    minute_end = now.replace(second=0, microsecond=0)
    minute_start = minute_end - __import__("datetime").timedelta(minutes=1)

    rows = db.execute(
        select(
            RawTelemetry.device_id,
            func.avg(RawTelemetry.ch1).label("ch1_avg"),
            func.avg(RawTelemetry.ch2).label("ch2_avg"),
            func.avg(RawTelemetry.ch3).label("ch3_avg"),
            func.avg(RawTelemetry.ch4).label("ch4_avg"),
            func.max(RawTelemetry.energy_kwh).label("energy_kwh"),
            func.max(RawTelemetry.voltage).label("voltage"),
            func.max(RawTelemetry.frequency).label("frequency"),
            func.max(RawTelemetry.power_factor).label("power_factor"),
            func.max(RawTelemetry.ch1_energy_kwh).label("ch1_energy_kwh"),
            func.max(RawTelemetry.ch2_energy_kwh).label("ch2_energy_kwh"),
            func.max(RawTelemetry.ch3_energy_kwh).label("ch3_energy_kwh"),
            func.max(RawTelemetry.ch4_energy_kwh).label("ch4_energy_kwh"),
            func.count().label("reading_count"),
        )
        .where(
            RawTelemetry.recorded_at >= minute_start,
            RawTelemetry.recorded_at < minute_end,
        )
        .group_by(RawTelemetry.device_id)
    ).all()

    if not rows:
        return 0

    count = 0
    for row in rows:
        telemetry = Telemetry(
            device_id=row.device_id,
            recorded_at=minute_start,
            energy_kwh=row.energy_kwh,
            voltage=row.voltage,
            frequency=row.frequency,
            power_factor=row.power_factor,
            ch1=row.ch1_avg,
            ch2=row.ch2_avg,
            ch3=row.ch3_avg,
            ch4=row.ch4_avg,
            ch1_energy_kwh=row.ch1_energy_kwh,
            ch2_energy_kwh=row.ch2_energy_kwh,
            ch3_energy_kwh=row.ch3_energy_kwh,
            ch4_energy_kwh=row.ch4_energy_kwh,
        )
        db.add(telemetry)
        count += 1

    db.execute(
        RawTelemetry.__table__.delete().where(
            RawTelemetry.recorded_at >= minute_start,
            RawTelemetry.recorded_at < minute_end,
        )
    )
    db.commit()
    return count


def cleanup_raw_telemetry(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=24)
    result = db.execute(
        RawTelemetry.__table__.delete().where(RawTelemetry.recorded_at < cutoff)
    )
    db.commit()
    return result.rowcount


def create_telemetry(db: Session, device_code: str, payload: TelemetryIn) -> Telemetry | None:
    device = db.scalar(select(Device).where(Device.code == device_code, Device.is_active.is_(True)))
    if device is None:
        return None
    if not verify_device_key(payload.device_key, device.device_key_hash):
        raise InvalidDeviceKeyError

    now = datetime.now(timezone.utc)
    recorded_at = payload.recorded_at or now
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
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
    ch_energies: list[Decimal | None] = [None, None, None, None]
    global_voltage = Decimal(str(settings.assumed_voltage))
    has_channels = len(channels) > 0

    for idx in range(4):
        ch_current = ch_currents[idx]
        if ch_current is None:
            continue
        ch_config = next((c for c in channels if c.channel_number == idx + 1), None)
        if has_channels and ch_config is None:
            continue
        ch_voltage = global_voltage if ch_config is None else ch_config.voltage
        ch_power_val = Decimal(str(float(ch_current) * float(ch_voltage)))
        prev_ch_energy = getattr(prev, f"ch{idx + 1}_energy_kwh", None) if prev else None
        delta_hours = (recorded_at - prev.recorded_at).total_seconds() / 3600 if prev else 0
        ch_energies[idx] = _calc_channel_energy(prev_ch_energy, ch_power_val, delta_hours)

    total_energy = sum(e for e in ch_energies if e is not None) or payload.energy_kwh

    telemetry = Telemetry(
        device_id=device.id,
        recorded_at=recorded_at,
        voltage=payload.voltage or global_voltage,
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
