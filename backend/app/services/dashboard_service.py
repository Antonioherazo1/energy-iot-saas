import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Numeric, Select, and_, case, desc, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.channel import DeviceChannel
from app.models.device import Device
from app.models.organization import OrganizationMember
from app.models.setting import OrganizationSetting
from app.models.raw_telemetry import RawTelemetry
from app.models.telemetry import Telemetry
from app.models.user import User

COL_TZ_OFFSET = func.make_interval(0, 0, 0, 0, 5)
MAX_DELTA_SECONDS = 120



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
            RawTelemetry.device_id,
            RawTelemetry.recorded_at,
            RawTelemetry.voltage,
            RawTelemetry.energy_kwh,
            RawTelemetry.frequency,
            RawTelemetry.power_factor,
            RawTelemetry.ch1,
            RawTelemetry.ch2,
            RawTelemetry.ch3,
            RawTelemetry.ch4,
            RawTelemetry.ch1_energy_kwh,
            RawTelemetry.ch2_energy_kwh,
            RawTelemetry.ch3_energy_kwh,
            RawTelemetry.ch4_energy_kwh,
            func.row_number()
            .over(partition_by=RawTelemetry.device_id, order_by=RawTelemetry.recorded_at.desc())
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
    result = []
    for row in rows:
        d = dict(row._mapping)
        power = Decimal("0")
        voltage = Decimal(str(d.get("voltage") or 0)) or Decimal("0")
        for ch_num in range(1, 5):
            ch_key = f"ch{ch_num}"
            ch_current = d.get(ch_key)
            if ch_current is not None and ch_current != 0:
                power += Decimal(str(ch_current)) * voltage
        d["power"] = power
        result.append(d)
    return result


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
            per_device_period.c.period,
            func.coalesce(func.sum(per_device_period.c.energy_kwh), 0).label("energy_kwh"),
            func.count().label("record_count"),
        )
        .group_by(per_device_period.c.period)
        .order_by(per_device_period.c.period)
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
    prev_delta_seconds = func.extract("epoch", Telemetry.recorded_at - prev_ts)
    delta_expr = prev_delta_seconds / 3600 / 1000
    energy_delta = dynamic_power * func.cast(delta_expr, Numeric(20, 10))

    shifted_ts = Telemetry.recorded_at - func.make_interval(0, 0, 0, shift_days) - COL_TZ_OFFSET
    shifted_bucket = func.date_trunc("month", shifted_ts).label("period")

    min_date = datetime.now(timezone.utc) - timedelta(days=safe_limit * 45)

    cte = (
        select(
            shifted_bucket,
            Telemetry.device_id,
            case(
                (and_(prev_ts.is_not(None), energy_delta > 0, prev_delta_seconds <= MAX_DELTA_SECONDS), energy_delta),
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
            Telemetry.recorded_at >= min_date,
        )
        .cte("energy_cte")
    )

    rows = db.execute(
        select(
            cte.c.period,
            func.coalesce(func.sum(case((cte.c.energy_delta > 0, cte.c.energy_delta), else_=0)), 0).label("energy_kwh"),
            func.count().label("record_count"),
        )
        .group_by(cte.c.period)
        .order_by(desc(cte.c.period))
        .limit(safe_limit)
    )
    return [
        {"period": row.period.date(), "energy_kwh": row.energy_kwh or Decimal("0"), "record_count": row.record_count}
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
    prev_delta_seconds = func.extract("epoch", Telemetry.recorded_at - prev_ts)
    delta_expr = prev_delta_seconds / 3600 / 1000
    delta_numeric = func.cast(delta_expr, Numeric(20, 10))

    bucket = func.date_trunc("day", Telemetry.recorded_at - COL_TZ_OFFSET).label("period")

    cte = (
        select(
            bucket,
            case((and_(prev_ts.is_not(None), ch_power_1 * delta_numeric > 0, prev_delta_seconds <= MAX_DELTA_SECONDS), ch_power_1 * delta_numeric), else_=0).label("en_ch1"),
            case((and_(prev_ts.is_not(None), ch_power_2 * delta_numeric > 0, prev_delta_seconds <= MAX_DELTA_SECONDS), ch_power_2 * delta_numeric), else_=0).label("en_ch2"),
            case((and_(prev_ts.is_not(None), ch_power_3 * delta_numeric > 0, prev_delta_seconds <= MAX_DELTA_SECONDS), ch_power_3 * delta_numeric), else_=0).label("en_ch3"),
            case((and_(prev_ts.is_not(None), ch_power_4 * delta_numeric > 0, prev_delta_seconds <= MAX_DELTA_SECONDS), ch_power_4 * delta_numeric), else_=0).label("en_ch4"),
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
    prev_delta_seconds = func.extract("epoch", Telemetry.recorded_at - prev_ts)
    delta_expr = prev_delta_seconds / 3600 / 1000
    energy_delta = dynamic_power * func.cast(delta_expr, Numeric(20, 10))

    bucket = func.date_trunc("day", Telemetry.recorded_at - COL_TZ_OFFSET).label("period")

    cte = (
        select(
            bucket,
            Telemetry.device_id,
            case(
                (and_(prev_ts.is_not(None), energy_delta > 0, prev_delta_seconds <= MAX_DELTA_SECONDS), energy_delta),
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


def get_channel_time_series(
    db: Session,
    user: User,
    organization_id: uuid.UUID | None = None,
    limit: int = 60,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    from sqlalchemy import union_all

    safe_limit = max(1, min(limit, 500))

    raw = select(
        RawTelemetry.recorded_at.label("recorded_at"),
        Device.name.label("device_name"),
        RawTelemetry.ch1,
        RawTelemetry.ch2,
        RawTelemetry.ch3,
        RawTelemetry.ch4,
        RawTelemetry.ch1_energy_kwh,
        RawTelemetry.ch2_energy_kwh,
        RawTelemetry.ch3_energy_kwh,
        RawTelemetry.ch4_energy_kwh,
    ).join(Device, Device.id == RawTelemetry.device_id).where(
        Device.organization_id.in_(organization_ids),
        or_(RawTelemetry.ch1.is_not(None), RawTelemetry.ch2.is_not(None),
            RawTelemetry.ch3.is_not(None), RawTelemetry.ch4.is_not(None)),
    )

    agg = select(
        Telemetry.recorded_at.label("recorded_at"),
        Device.name.label("device_name"),
        Telemetry.ch1,
        Telemetry.ch2,
        Telemetry.ch3,
        Telemetry.ch4,
        Telemetry.ch1_energy_kwh,
        Telemetry.ch2_energy_kwh,
        Telemetry.ch3_energy_kwh,
        Telemetry.ch4_energy_kwh,
    ).join(Device, Device.id == Telemetry.device_id).where(
        Device.organization_id.in_(organization_ids),
        or_(Telemetry.ch1.is_not(None), Telemetry.ch2.is_not(None),
            Telemetry.ch3.is_not(None), Telemetry.ch4.is_not(None)),
    )

    union_q = union_all(raw, agg).cte()
    rows = db.execute(
        select(union_q)
        .order_by(union_q.c.recorded_at.desc())
        .limit(safe_limit)
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
    from sqlalchemy import union_all

    raw = select(
        RawTelemetry.recorded_at.label("recorded_at"),
        RawTelemetry.ch1,
        RawTelemetry.ch2,
        RawTelemetry.ch3,
        RawTelemetry.ch4,
    ).where(
        RawTelemetry.device_id == device.id,
        RawTelemetry.recorded_at >= since,
        or_(RawTelemetry.ch1.is_not(None), RawTelemetry.ch2.is_not(None),
            RawTelemetry.ch3.is_not(None), RawTelemetry.ch4.is_not(None)),
    )

    agg = select(
        Telemetry.recorded_at.label("recorded_at"),
        Telemetry.ch1,
        Telemetry.ch2,
        Telemetry.ch3,
        Telemetry.ch4,
    ).where(
        Telemetry.device_id == device.id,
        Telemetry.recorded_at >= since,
        or_(Telemetry.ch1.is_not(None), Telemetry.ch2.is_not(None),
            Telemetry.ch3.is_not(None), Telemetry.ch4.is_not(None)),
    )

    union_q = union_all(raw, agg).cte()
    rows = db.execute(
        select(union_q).order_by(union_q.c.recorded_at)
    )
    return [dict(row._mapping) for row in rows]


def get_channel_series(
    db: Session,
    user: User,
    device_id: uuid.UUID,
    since: datetime,
    until: datetime,
) -> list[dict]:
    org_ids = get_accessible_organization_ids(db, user)
    device = db.get(Device, device_id)
    if device is None or device.organization_id not in org_ids:
        return []

    channels_map = {
        ch.channel_number: ch
        for ch in db.scalars(
            select(DeviceChannel).where(
                DeviceChannel.device_id == device.id,
                DeviceChannel.is_active.is_(True),
            )
        )
    }

    from sqlalchemy import union_all

    raw = select(
        RawTelemetry.recorded_at.label("recorded_at"),
        RawTelemetry.ch1,
        RawTelemetry.ch2,
        RawTelemetry.ch3,
        RawTelemetry.ch4,
        RawTelemetry.ch1_energy_kwh,
        RawTelemetry.ch2_energy_kwh,
        RawTelemetry.ch3_energy_kwh,
        RawTelemetry.ch4_energy_kwh,
    ).where(
        RawTelemetry.device_id == device.id,
        RawTelemetry.recorded_at >= since,
        RawTelemetry.recorded_at <= until,
        or_(RawTelemetry.ch1.is_not(None), RawTelemetry.ch2.is_not(None),
            RawTelemetry.ch3.is_not(None), RawTelemetry.ch4.is_not(None)),
    )

    agg = select(
        Telemetry.recorded_at.label("recorded_at"),
        Telemetry.ch1,
        Telemetry.ch2,
        Telemetry.ch3,
        Telemetry.ch4,
        Telemetry.ch1_energy_kwh,
        Telemetry.ch2_energy_kwh,
        Telemetry.ch3_energy_kwh,
        Telemetry.ch4_energy_kwh,
    ).where(
        Telemetry.device_id == device.id,
        Telemetry.recorded_at >= since,
        Telemetry.recorded_at <= until,
        or_(Telemetry.ch1.is_not(None), Telemetry.ch2.is_not(None),
            Telemetry.ch3.is_not(None), Telemetry.ch4.is_not(None)),
    )

    union_q = union_all(raw, agg).cte()
    rows = db.execute(
        select(union_q).order_by(union_q.c.recorded_at)
    )

    result = []
    for row in rows:
        entry = dict(row._mapping)
        for ch_num in range(1, 5):
            ch_current = entry.get(f"ch{ch_num}")
            if ch_current is not None:
                ch_config = channels_map.get(ch_num)
                ch_voltage = ch_config.voltage if ch_config else Decimal("110")
                entry[f"ch{ch_num}_power"] = Decimal(str(ch_current)) * ch_voltage
        result.append(entry)
    return result


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
            or_(Telemetry.ch1.is_not(None), Telemetry.ch2.is_not(None),
                Telemetry.ch3.is_not(None), Telemetry.ch4.is_not(None)),
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
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    now = datetime.now(timezone.utc)
    start = start_date if start_date else (now - timedelta(days=days))

    filters = [Device.organization_id.in_(organization_ids), Telemetry.recorded_at >= start]
    if end_date:
        filters.append(Telemetry.recorded_at <= end_date)

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
    prev_delta_seconds = func.extract("epoch", Telemetry.recorded_at - prev_ts)
    delta_expr = prev_delta_seconds / 3600 / 1000
    energy_delta = total_power * func.cast(delta_expr, Numeric(20, 10))

    bucket = func.date_trunc("day", Telemetry.recorded_at - COL_TZ_OFFSET).label("period")

    cte = (
        select(
            bucket,
            Telemetry.device_id,
            case(
                (and_(prev_ts.is_not(None), energy_delta > 0, prev_delta_seconds <= MAX_DELTA_SECONDS), energy_delta),
                else_=0,
            ).label("energy_delta"),
        )
        .join(Device, Device.id == Telemetry.device_id)
        .outerjoin(c1, and_(c1.device_id == Telemetry.device_id, c1.channel_number == 1, c1.is_active == True))
        .outerjoin(c2, and_(c2.device_id == Telemetry.device_id, c2.channel_number == 2, c2.is_active == True))
        .outerjoin(c3, and_(c3.device_id == Telemetry.device_id, c3.channel_number == 3, c3.is_active == True))
        .outerjoin(c4, and_(c4.device_id == Telemetry.device_id, c4.channel_number == 4, c4.is_active == True))
        .where(and_(*filters))
        .cte("recalc_cte")
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


def get_energy_slope(
    db: Session,
    user: User,
    organization_id: uuid.UUID | None = None,
    limit: int = 30,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []

    daily = recalculate_daily_energy(db=db, user=user, days=limit, organization_id=organization_id, start_date=start_date, end_date=end_date)

    membership = db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    kwh_rate = Decimal("800")
    if membership:
        setting = db.scalar(
            select(OrganizationSetting).where(
                OrganizationSetting.organization_id.in_(organization_ids),
                OrganizationSetting.key == "kwh_rate",
            )
        )
        if setting:
            kwh_rate = Decimal(setting.value)

    result = []
    prev_kwh = Decimal("0")
    for item in daily:
        kwh = item["energy_kwh"]
        cost = kwh * kwh_rate
        slope_kwh = kwh - prev_kwh
        slope_cost = slope_kwh * kwh_rate
        result.append({
            "period": item["period"],
            "energy_kwh": kwh,
            "cost": cost,
            "slope_kwh": slope_kwh,
            "slope_cost": slope_cost,
        })
        prev_kwh = kwh

    return result


def get_hourly_energy(
    db: Session,
    user: User,
    date: str,
    device_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    bucket_seconds: int = 600,
) -> list[dict]:
    organization_ids = get_accessible_organization_ids(db, user, organization_id)
    if not organization_ids:
        return []
    if device_id:
        dev = db.scalar(
            select(Device).where(Device.id == device_id, Device.organization_id.in_(organization_ids))
        )
        if not dev:
            return []
        device_ids = [device_id]
    else:
        device_ids = db.scalars(
            select(Device.id).where(Device.organization_id.in_(organization_ids))
        ).all()
        if not device_ids:
            return []

    dt = datetime.fromisoformat(date)
    day_start = dt.replace(hour=5, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    membership = db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    kwh_rate = Decimal("800")
    if membership:
        setting = db.scalar(
            select(OrganizationSetting).where(
                OrganizationSetting.organization_id.in_(organization_ids),
                OrganizationSetting.key == "kwh_rate",
            )
        )
        if setting:
            kwh_rate = Decimal(setting.value)

    rows = db.execute(
        select(Telemetry.device_id, Telemetry.recorded_at,
               Telemetry.ch1_energy_kwh, Telemetry.ch2_energy_kwh,
               Telemetry.ch3_energy_kwh, Telemetry.ch4_energy_kwh,
               Telemetry.ch1, Telemetry.ch2, Telemetry.ch3, Telemetry.ch4)
        .where(
            Telemetry.device_id.in_(device_ids),
            Telemetry.recorded_at >= day_start,
            Telemetry.recorded_at < day_end,
        )
        .order_by(Telemetry.device_id, Telemetry.recorded_at)
    )

    def bucket_time_key(col_time: datetime) -> str:
        total_sec = col_time.hour * 3600 + col_time.minute * 60 + col_time.second
        bucket_start = total_sec // bucket_seconds * bucket_seconds
        h = bucket_start // 3600
        m = (bucket_start % 3600) // 60
        s = bucket_start % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def total_energy(row) -> Decimal:
        return (row.ch1_energy_kwh or Decimal("0")) + (row.ch2_energy_kwh or Decimal("0")) + \
               (row.ch3_energy_kwh or Decimal("0")) + (row.ch4_energy_kwh or Decimal("0"))

    buckets: dict[str, Decimal] = {}
    current_sums: dict[str, Decimal] = {}
    current_counts: dict[str, int] = {}
    prev_by_device: dict[uuid.UUID, Decimal] = {}

    for row in rows:
        cur = total_energy(row)
        prev_val = prev_by_device.get(row.device_id)
        if prev_val is not None:
            diff = cur - prev_val
            if diff > 0:
                col_time = row.recorded_at - timedelta(hours=5)
                key = bucket_time_key(col_time)
                buckets[key] = buckets.get(key, Decimal("0")) + diff
        prev_by_device[row.device_id] = cur

        total_current = Decimal("0")
        current_count = 0
        for ch in (row.ch1, row.ch2, row.ch3, row.ch4):
            if ch is not None:
                total_current += ch
                current_count += 1
        if current_count > 0:
            avg_row_current = total_current / current_count
            col_time = row.recorded_at - timedelta(hours=5)
            key = bucket_time_key(col_time)
            current_sums[key] = current_sums.get(key, Decimal("0")) + avg_row_current
            current_counts[key] = current_counts.get(key, 0) + 1

    result = []
    for key in sorted(buckets.keys()):
        kwh = buckets[key]
        cnt = current_counts.get(key, 1)
        avg_current = current_sums.get(key, Decimal("0")) / cnt
        result.append({
            "time": key,
            "energy_kwh": kwh or Decimal("0"),
            "cost": kwh * kwh_rate,
            "avg_current_a": avg_current,
        })
    return result
