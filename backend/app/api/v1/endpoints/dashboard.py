import csv
import io
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.telemetry import Telemetry
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryRead, DeviceStatusRead, EnergyBucketRead, LatestTelemetryRead
from app.services.dashboard_service import get_accessible_organization_ids, get_device_status, get_energy_by_period, get_latest_telemetry, get_summary

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryRead)
def dashboard_summary(
    organization_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return get_summary(db=db, user=current_user, organization_id=organization_id)


@router.get("/devices/status", response_model=list[DeviceStatusRead])
def devices_status(
    organization_id: uuid.UUID | None = None,
    online_window_minutes: int = Query(default=5, ge=1, le=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return get_device_status(
        db=db,
        user=current_user,
        organization_id=organization_id,
        online_window_minutes=online_window_minutes,
    )


@router.get("/telemetry/latest", response_model=list[LatestTelemetryRead])
def telemetry_latest(
    organization_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return get_latest_telemetry(db=db, user=current_user, organization_id=organization_id)


@router.get("/energy/daily", response_model=list[EnergyBucketRead])
def energy_daily(
    organization_id: uuid.UUID | None = None,
    limit: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return get_energy_by_period(db=db, user=current_user, organization_id=organization_id, period="day", limit=limit)


@router.get("/channels/latest")
def channels_latest(
    organization_id: uuid.UUID | None = None,
    limit: int = Query(default=60, ge=10, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    from app.services.dashboard_service import get_channel_time_series
    return get_channel_time_series(db=db, user=current_user, organization_id=organization_id, limit=limit)


@router.get("/energy/monthly", response_model=list[EnergyBucketRead])
def energy_monthly(
    organization_id: uuid.UUID | None = None,
    limit: int = Query(default=12, ge=1, le=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return get_energy_by_period(db=db, user=current_user, organization_id=organization_id, period="month", limit=limit)


@router.get("/telemetry/csv")
def telemetry_csv(
    organization_id: uuid.UUID | None = None,
    limit: int = Query(default=500, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    organization_ids = get_accessible_organization_ids(db, current_user, organization_id)
    if not organization_ids:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "device_id", "device_name", "device_code",
            "recorded_at", "voltage", "current", "power", "energy_kwh",
            "frequency", "power_factor",
            "ch1_a", "ch2_a", "ch3_a", "ch4_a",
        ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=telemetria.csv"},
        )

    query = (
        select(Telemetry, Device)
        .join(Device, Telemetry.device_id == Device.id)
        .where(Device.organization_id.in_(organization_ids))
        .order_by(Telemetry.recorded_at.desc())
        .limit(limit)
    )
    rows = db.execute(query).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "device_id", "device_name", "device_code",
        "recorded_at", "voltage", "current", "power", "energy_kwh",
        "frequency", "power_factor",
        "ch1_a", "ch2_a", "ch3_a", "ch4_a",
    ])
    for telemetry, device in rows:
        writer.writerow([
            telemetry.device_id,
            device.name,
            device.code,
            telemetry.recorded_at.isoformat() if telemetry.recorded_at else "",
            telemetry.voltage,
            telemetry.current,
            telemetry.power,
            telemetry.energy_kwh,
            telemetry.frequency,
            telemetry.power_factor,
            telemetry.ch1,
            telemetry.ch2,
            telemetry.ch3,
            telemetry.ch4,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=telemetria.csv"},
    )

