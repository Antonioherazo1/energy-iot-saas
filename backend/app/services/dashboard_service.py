import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Numeric, Select, and_, case, desc, func, select
from sqlalchemy.orm import Session, aliased

from app.models.channel import DeviceChannel
from app.models.device import Device
from app.models.organization import OrganizationMember
from app.models.telemetry import Telemetry
from app.models.user import User

COL_TZ_OFFSET = func.make_interval(0, 0, 0, 0, 5)


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
    bucket = func.date_trunc(period, Telemetry.recorded_at - COL_TZ_OFFSET).label("period")
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
            cte.c.period,
            func.coalesce(func.sum(case((cte.c.energy_delta > 0, cte.c.energy_delta), else_=0)), 0).label("energy_kwh"),
            func.count().label("record_count"),
        )
        .group_by(cte.c.period)
        .order_by(cte.c.period)
    )
    return [
        {"period": row.period.date(), "energy_kwh": row.energy_kwh or Decimal("0"), "record_count": row.record_count}
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

    c1 = aliased(DeviceChannel, name="c1")
    c2 = aliased(DeviceChannel, name="c2")
    c3 = aliased(DeviceChannel, name="c3")
    c4 = aliased(DeviceChannel, name="c4")

    ch_power_1 = case((c1.id.is_not(None), func.coalesce(Telemetry.ch1, 0) * c1.voltage), else_=0)
    ch_power_2 = case((c2.id.is_not(None), func.coalesce(Telemetry.ch2, 0) * c2.voltage), else_=0)
    ch_power_3 = case((c3.id.is_not(None), func.coalesce(Telemetry.ch3, 0) * c3.voltage), else_=0)
    ch_power_4 = case((c4.id.is_not(None), func.coalesce(Telemetry.ch4, 0) * c4.voltage), else_=0)
    dynamic_power = ch_power_1 + ch_power_2 + ch_power_3 + ch_power_4

    prev_ts = func.lag(Telemetry.recorded_at).over(
        partition_by=Telemetry.device_id,
        order_by=Telemetry.recorded_at,
    )
    delta_expr = func.extract("epoch", Telemetry.recorded_at - prev_ts) / 3600 / 1000
    energy_delta = dynamic_power * func.cast(delta_expr, Numeric(20, 10))

    shifted_ts = Telemetry.recorded_at - func.make_interval(0, 0, 0, shift_days) - COL_TZ_OFFSET
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
        .outerjoin(c1, and_(c1.device_id == Telemetry.device_id, c1.channel_number == 1, c1.is_active == True))
        .outerjoin(c2, and_(c2.device_id == Telemetry.device_id, c2.channel_number == 2, c2.is_active == True))
        .outerjoin(c3, and_(c3.device_id == Telemetry.device_id, c3.channel_number == 3, c3.is_active == True))
        .outerjoin(c4, and_(c4.device_id == Telemetry.device_id, c4.channel_number == 4, c4.is_active == True))
        .where(
            Device.organization_id.in_(organization_ids),
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


def get_billing_daily_per_channel(
    db: Session,
    user: User,
    device_id: uuid.UUID,
    organization_id: uuid.UUID | None = None,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    device = db.get(Device, device_id)
    if device is None or device.organization_id not in organization_ids:
        return []

    channels_config = {ch.channel_number: ch for ch in db.scalars(
        select(DeviceChannel).where(DeviceChannel.device_id == device.id, DeviceChannel.is_active.is_(True))
    )}

    now = datetime.now(timezone.utc)
    col_midnight = now.replace(hour=5, minute=0, second=0, microsecond=0)
    if col_midnight > now:
        col_midnight -= timedelta(days=1)
    day_start = col_midnight

    c1 = aliased(DeviceChannel, name="c1")
    c2 = aliased(DeviceChannel, name="c2")
    c3 = aliased(DeviceChannel, name="c3")
    c4 = aliased(DeviceChannel, name="c4")

    ch_power_1 = case((c1.id.is_not(None), func.coalesce(Telemetry.ch1, 0) * c1.voltage), else_=0)
    ch_power_2 = case((c2.id.is_not(None), func.coalesce(Telemetry.ch2, 0) * c2.voltage), else_=0)
    ch_power_3 = case((c3.id.is_not(None), func.coalesce(Telemetry.ch3, 0) * c3.voltage), else_=0)
    ch_power_4 = case((c4.id.is_not(None), func.coalesce(Telemetry.ch4, 0) * c4.voltage), else_=0)

    prev_ts = func.lag(Telemetry.recorded_at).over(
        partition_by=Telemetry.device_id,
        order_by=Telemetry.recorded_at,
    )
    delta_expr = func.extract("epoch", Telemetry.recorded_at - prev_ts) / 3600 / 1000
    delta_numeric = func.cast(delta_expr, Numeric(20, 10))

    bucket = func.date_trunc("day", Telemetry.recorded_at - COL_TZ_OFFSET).label("period")

    cte = (
        select(
            bucket,
            case((and_(prev_ts.is_not(None), ch_power_1 * delta_numeric > 0), ch_power_1 * delta_numeric), else_=0).label("en_ch1"),
            case((and_(prev_ts.is_not(None), ch_power_2 * delta_numeric > 0), ch_power_2 * delta_numeric), else_=0).label("en_ch2"),
            case((and_(prev_ts.is_not(None), ch_power_3 * delta_numeric > 0), ch_power_3 * delta_numeric), else_=0).label("en_ch3"),
            case((and_(prev_ts.is_not(None), ch_power_4 * delta_numeric > 0), ch_power_4 * delta_numeric), else_=0).label("en_ch4"),
        )
        .join(Device, Device.id == Telemetry.device_id)
        .outerjoin(c1, and_(c1.device_id == Telemetry.device_id, c1.channel_number == 1, c1.is_active == True))
        .outerjoin(c2, and_(c2.device_id == Telemetry.device_id, c2.channel_number == 2, c2.is_active == True))
        .outerjoin(c3, and_(c3.device_id == Telemetry.device_id, c3.channel_number == 3, c3.is_active == True))
        .outerjoin(c4, and_(c4.device_id == Telemetry.device_id, c4.channel_number == 4, c4.is_active == True))
        .where(
            Telemetry.device_id == device.id,
            Telemetry.recorded_at >= day_start,
        )
        .cte("energy_cte")
    )

    rows = db.execute(
        select(
            func.coalesce(func.sum(cte.c.en_ch1), 0).label("ch1"),
            func.coalesce(func.sum(cte.c.en_ch2), 0).label("ch2"),
            func.coalesce(func.sum(cte.c.en_ch3), 0).label("ch3"),
            func.coalesce(func.sum(cte.c.en_ch4), 0).label("ch4"),
        )
    ).one()

    result = []
    ch_map = {1: "ch1", 2: "ch2", 3: "ch3", 4: "ch4"}
    for ch_num in range(1, 5):
        config = channels_config.get(ch_num)
        if config is None:
            continue
        energy = getattr(rows, ch_map[ch_num], Decimal("0"))
        result.append({
            "channel_number": ch_num,
            "channel_name": config.name,
            "energy_kwh": energy or Decimal("0"),
        })
    return result


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
    period_start = now.replace(day=billing_start_day, hour=5, minute=0, second=0, microsecond=0)
    if period_start > now:
        period_start = (period_start.replace(day=1) - timedelta(days=1)).replace(day=billing_start_day, hour=5, minute=0, second=0, microsecond=0)

    c1 = aliased(DeviceChannel, name="c1")
    c2 = aliased(DeviceChannel, name="c2")
    c3 = aliased(DeviceChannel, name="c3")
    c4 = aliased(DeviceChannel, name="c4")

    ch_power_1 = case((c1.id.is_not(None), func.coalesce(Telemetry.ch1, 0) * c1.voltage), else_=0)
    ch_power_2 = case((c2.id.is_not(None), func.coalesce(Telemetry.ch2, 0) * c2.voltage), else_=0)
    ch_power_3 = case((c3.id.is_not(None), func.coalesce(Telemetry.ch3, 0) * c3.voltage), else_=0)
    ch_power_4 = case((c4.id.is_not(None), func.coalesce(Telemetry.ch4, 0) * c4.voltage), else_=0)
    dynamic_power = ch_power_1 + ch_power_2 + ch_power_3 + ch_power_4

    prev_ts = func.lag(Telemetry.recorded_at).over(
        partition_by=Telemetry.device_id,
        order_by=Telemetry.recorded_at,
    )
    delta_expr = func.extract("epoch", Telemetry.recorded_at - prev_ts) / 3600 / 1000
    energy_delta = dynamic_power * func.cast(delta_expr, Numeric(20, 10))

    bucket = func.date_trunc("day", Telemetry.recorded_at - COL_TZ_OFFSET).label("period")

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
        .outerjoin(c1, and_(c1.device_id == Telemetry.device_id, c1.channel_number == 1, c1.is_active == True))
        .outerjoin(c2, and_(c2.device_id == Telemetry.device_id, c2.channel_number == 2, c2.is_active == True))
        .outerjoin(c3, and_(c3.device_id == Telemetry.device_id, c3.channel_number == 3, c3.is_active == True))
        .outerjoin(c4, and_(c4.device_id == Telemetry.device_id, c4.channel_number == 4, c4.is_active == True))
        .where(
            Device.organization_id.in_(organization_ids),
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

    day_start = datetime.fromisoformat(date).replace(hour=5, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1) - timedelta(seconds=1)

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


def recalculate_daily_energy(
    db: Session,
    user: User,
    days: int = 30,
    organization_id: uuid.UUID | None = None,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    c1 = aliased(DeviceChannel, name="c1")
    c2 = aliased(DeviceChannel, name="c2")
    c3 = aliased(DeviceChannel, name="c3")
    c4 = aliased(DeviceChannel, name="c4")

    ch_power_1 = case((c1.id.is_not(None), func.coalesce(Telemetry.ch1, 0) * c1.voltage), else_=0)
    ch_power_2 = case((c2.id.is_not(None), func.coalesce(Telemetry.ch2, 0) * c2.voltage), else_=0)
    ch_power_3 = case((c3.id.is_not(None), func.coalesce(Telemetry.ch3, 0) * c3.voltage), else_=0)
    ch_power_4 = case((c4.id.is_not(None), func.coalesce(Telemetry.ch4, 0) * c4.voltage), else_=0)
    total_power = ch_power_1 + ch_power_2 + ch_power_3 + ch_power_4

    prev_ts = func.lag(Telemetry.recorded_at).over(
        partition_by=Telemetry.device_id,
        order_by=Telemetry.recorded_at,
    )
    delta_expr = func.extract("epoch", Telemetry.recorded_at - prev_ts) / 3600 / 1000
    energy_delta = total_power * func.cast(delta_expr, Numeric(20, 10))

    bucket = func.date_trunc("day", Telemetry.recorded_at - COL_TZ_OFFSET).label("period")

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
        .outerjoin(c1, and_(c1.device_id == Telemetry.device_id, c1.channel_number == 1, c1.is_active == True))
        .outerjoin(c2, and_(c2.device_id == Telemetry.device_id, c2.channel_number == 2, c2.is_active == True))
        .outerjoin(c3, and_(c3.device_id == Telemetry.device_id, c3.channel_number == 3, c3.is_active == True))
        .outerjoin(c4, and_(c4.device_id == Telemetry.device_id, c4.channel_number == 4, c4.is_active == True))
        .where(
            Device.organization_id.in_(organization_ids),
            Telemetry.recorded_at >= start,
        )
        .cte("recalc_cte")
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

