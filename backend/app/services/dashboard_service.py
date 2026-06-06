import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Numeric, Select, and_, case, desc, func, select
from sqlalchemy.orm import Session

from app.models.channel import DeviceChannel
from app.models.device import Device
from app.models.organization import OrganizationMember
from app.models.telemetry import Telemetry
from app.models.user import User


def get_accessible_organization_ids(db: Session, user: User, organization_id: uuid.UUID | None = None) -> list[uuid.UUID]:
    query = select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user.id)
    organization_ids = list(db.scalars(query))

    if organization_id is None:
        return organization_ids

    if organization_id not in organization_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to organization")
    return [organization_id]


def get_device_status(
    db: Session,
    user: User,
    organization_id: uuid.UUID | None = None,
    online_window_minutes: int = 5,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    online_after = datetime.now(timezone.utc) - timedelta(minutes=online_window_minutes)
    rows = db.execute(
        select(
            Device.id.label("device_id"),
            Device.name,
            Device.code,
            Device.is_active,
            Device.last_seen_at,
            case((Device.last_seen_at >= online_after, True), else_=False).label("is_online"),
        )
        .where(Device.organization_id.in_(organization_ids))
        .order_by(Device.name)
    )
    return [dict(row._mapping) for row in rows]


def latest_telemetry_query(organization_ids: list[uuid.UUID]) -> Select:
    latest = (
        select(
            Telemetry.device_id,
            Telemetry.recorded_at,
            Telemetry.voltage,
            Telemetry.current,
            Telemetry.power,
            Telemetry.energy_kwh,
            Telemetry.frequency,
            Telemetry.power_factor,
            Telemetry.ch1,
            Telemetry.ch2,
            Telemetry.ch3,
            Telemetry.ch4,
            Telemetry.ch1_energy_kwh,
            Telemetry.ch2_energy_kwh,
            Telemetry.ch3_energy_kwh,
            Telemetry.ch4_energy_kwh,
            func.row_number()
            .over(partition_by=Telemetry.device_id, order_by=Telemetry.recorded_at.desc())
            .label("row_number"),
        )
        .subquery()
    )

    return (
        select(
            Device.id.label("device_id"),
            Device.name.label("device_name"),
            Device.code.label("device_code"),
            latest.c.recorded_at,
            latest.c.voltage,
            latest.c.current,
            latest.c.power,
            latest.c.energy_kwh,
            latest.c.frequency,
            latest.c.power_factor,
            latest.c.ch1,
            latest.c.ch2,
            latest.c.ch3,
            latest.c.ch4,
            latest.c.ch1_energy_kwh,
            latest.c.ch2_energy_kwh,
            latest.c.ch3_energy_kwh,
            latest.c.ch4_energy_kwh,
        )
        .outerjoin(latest, and_(latest.c.device_id == Device.id, latest.c.row_number == 1))
        .where(Device.organization_id.in_(organization_ids))
        .order_by(Device.name)
    )


def get_latest_telemetry(db: Session, user: User, organization_id: uuid.UUID | None = None) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    rows = db.execute(latest_telemetry_query(organization_ids))
    return [dict(row._mapping) for row in rows]


def get_energy_by_period(
    db: Session,
    user: User,
    period: str,
    organization_id: uuid.UUID | None = None,
    limit: int = 30,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    safe_limit = max(1, min(limit, 365))
    bucket = func.date_trunc(period, Telemetry.recorded_at).label("period")
    per_device_period = (
        select(
            bucket,
            Telemetry.device_id,
            (func.max(Telemetry.energy_kwh) - func.min(Telemetry.energy_kwh)).label("energy_kwh"),
        )
        .join(Device, Device.id == Telemetry.device_id)
        .where(Device.organization_id.in_(organization_ids), Telemetry.energy_kwh.is_not(None))
        .group_by(bucket, Telemetry.device_id)
        .subquery()
    )

    rows = db.execute(
        select(
            per_device_period.c.period,
            func.coalesce(func.sum(per_device_period.c.energy_kwh), 0).label("energy_kwh"),
        )
        .group_by(per_device_period.c.period)
        .order_by(desc(per_device_period.c.period))
        .limit(safe_limit)
    )
    return [
        {"period": row.period.date(), "energy_kwh": row.energy_kwh or Decimal("0")}
        for row in rows
    ]


def get_billing_monthly_energy(
    db: Session,
    user: User,
    billing_start_day: int = 1,
    limit: int = 6,
    organization_id: uuid.UUID | None = None,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    safe_limit = max(1, min(limit, 24))
    shift_days = billing_start_day - 1

    prev_ts = func.lag(Telemetry.recorded_at).over(
        partition_by=Telemetry.device_id,
        order_by=Telemetry.recorded_at,
    )
    delta_expr = func.extract("epoch", Telemetry.recorded_at - prev_ts) / 3600 / 1000
    energy_delta = Telemetry.power * func.cast(delta_expr, Numeric(20, 10))

    shifted_ts = Telemetry.recorded_at - func.make_interval(0, 0, 0, shift_days)
    shifted_bucket = func.date_trunc("month", shifted_ts).label("period")

    cte = (
        select(
            shifted_bucket,
            Telemetry.device_id,
            case(
                (and_(prev_ts.is_not(None), energy_delta > 0), energy_delta),
                else_=0,
            ).label("energy_delta"),
        )
        .join(Device, Device.id == Telemetry.device_id)
        .where(
            Device.organization_id.in_(organization_ids),
            Telemetry.power.is_not(None),
            Telemetry.power >= 0,
        )
        .cte("energy_cte")
    )

    rows = db.execute(
        select(
            cte.c.period,
            func.coalesce(func.sum(cte.c.energy_delta), 0).label("energy_kwh"),
        )
        .where(cte.c.energy_delta > 0)
        .group_by(cte.c.period)
        .order_by(desc(cte.c.period))
        .limit(safe_limit)
    )
    return [
        {"period": row.period.date(), "energy_kwh": row.energy_kwh or Decimal("0")}
        for row in rows
    ]


def get_billing_current_daily(
    db: Session,
    user: User,
    billing_start_day: int = 1,
    organization_id: uuid.UUID | None = None,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    now = datetime.now(timezone.utc)
    period_start = now.replace(day=billing_start_day, hour=0, minute=0, second=0, microsecond=0)
    if period_start > now:
        period_start = (period_start.replace(day=1) - timedelta(days=1)).replace(day=billing_start_day, hour=0, minute=0, second=0, microsecond=0)

    prev_ts = func.lag(Telemetry.recorded_at).over(
        partition_by=Telemetry.device_id,
        order_by=Telemetry.recorded_at,
    )
    delta_expr = func.extract("epoch", Telemetry.recorded_at - prev_ts) / 3600 / 1000
    energy_delta = Telemetry.power * func.cast(delta_expr, Numeric(20, 10))

    bucket = func.date_trunc("day", Telemetry.recorded_at).label("period")

    cte = (
        select(
            bucket,
            Telemetry.device_id,
            case(
                (and_(prev_ts.is_not(None), energy_delta > 0), energy_delta),
                else_=0,
            ).label("energy_delta"),
        )
        .join(Device, Device.id == Telemetry.device_id)
        .where(
            Device.organization_id.in_(organization_ids),
            Telemetry.power.is_not(None),
            Telemetry.power >= 0,
            Telemetry.recorded_at >= period_start,
        )
        .cte("energy_cte")
    )

    rows = db.execute(
        select(
            cte.c.period,
            func.coalesce(func.sum(cte.c.energy_delta), 0).label("energy_kwh"),
        )
        .where(cte.c.energy_delta > 0)
        .group_by(cte.c.period)
        .order_by(cte.c.period)
    )
    return [
        {"period": row.period.date(), "energy_kwh": row.energy_kwh or Decimal("0")}
        for row in rows
    ]


def get_channel_time_series(
    db: Session,
    user: User,
    organization_id: uuid.UUID | None = None,
    limit: int = 60,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    rows = db.execute(
        select(
            Telemetry.recorded_at,
            Device.name.label("device_name"),
            Telemetry.ch1,
            Telemetry.ch2,
            Telemetry.ch3,
            Telemetry.ch4,
            Telemetry.power,
            Telemetry.ch1_energy_kwh,
            Telemetry.ch2_energy_kwh,
            Telemetry.ch3_energy_kwh,
            Telemetry.ch4_energy_kwh,
        )
        .join(Device, Device.id == Telemetry.device_id)
        .where(
            Device.organization_id.in_(organization_ids),
            Telemetry.ch1.is_not(None),
        )
        .order_by(Telemetry.recorded_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    result = [dict(row._mapping) for row in rows]
    result.reverse()
    return result


def get_realtime_currents(
    db: Session,
    user: User,
    device_id: uuid.UUID,
    minutes: int = 10,
) -> list[dict]:
    org_ids = get_accessible_organization_ids(db, user)
    device = db.get(Device, device_id)
    if device is None or device.organization_id not in org_ids:
        return []

    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    rows = db.execute(
        select(
            Telemetry.recorded_at,
            Telemetry.ch1,
            Telemetry.ch2,
            Telemetry.ch3,
            Telemetry.ch4,
        )
        .where(
            Telemetry.device_id == device.id,
            Telemetry.recorded_at >= since,
            Telemetry.ch1.is_not(None),
        )
        .order_by(Telemetry.recorded_at)
    )
    return [dict(row._mapping) for row in rows]


def get_channel_day_series(
    db: Session,
    user: User,
    device_id: uuid.UUID,
    date: str,
) -> list[dict]:
    org_ids = get_accessible_organization_ids(db, user)
    device = db.get(Device, device_id)
    if device is None or device.organization_id not in org_ids:
        return []

    day_start = datetime.fromisoformat(date).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)

    channels_map = {
        ch.channel_number: ch
        for ch in db.scalars(
            select(DeviceChannel).where(
                DeviceChannel.device_id == device.id,
                DeviceChannel.is_active.is_(True),
            )
        )
    }

    rows = db.execute(
        select(
            Telemetry.recorded_at,
            Telemetry.ch1,
            Telemetry.ch2,
            Telemetry.ch3,
            Telemetry.ch4,
            Telemetry.ch1_energy_kwh,
            Telemetry.ch2_energy_kwh,
            Telemetry.ch3_energy_kwh,
            Telemetry.ch4_energy_kwh,
        )
        .where(
            Telemetry.device_id == device.id,
            Telemetry.recorded_at >= day_start,
            Telemetry.recorded_at <= day_end,
            Telemetry.ch1.is_not(None),
        )
        .order_by(Telemetry.recorded_at)
    )

    result = []
    for row in rows:
        entry = dict(row._mapping)
        for ch_num in range(1, 5):
            ch_current = entry.get(f"ch{ch_num}")
            ch_config = channels_map.get(ch_num)
            ch_voltage = ch_config.voltage if ch_config else Decimal("110")
            entry[f"ch{ch_num}_power"] = ch_current * ch_voltage if ch_current else None
        result.append(entry)
    return result


def get_summary(
    db: Session,
    user: User,
    organization_id: uuid.UUID | None = None,
    online_window_minutes: int = 5,
) -> dict:
    statuses = get_device_status(db, user, organization_id, online_window_minutes)
    latest = get_latest_telemetry(db, user, organization_id)

    online_devices = sum(1 for item in statuses if item["is_online"])
    current_power = sum((item["power"] or Decimal("0")) for item in latest)
    latest_energy_kwh = sum((item["energy_kwh"] or Decimal("0")) for item in latest)

    return {
        "total_devices": len(statuses),
        "online_devices": online_devices,
        "offline_devices": len(statuses) - online_devices,
        "current_power": current_power,
        "latest_energy_kwh": latest_energy_kwh,
    }

