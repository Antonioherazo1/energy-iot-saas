import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryRead, DeviceStatusRead, EnergyBucketRead, LatestTelemetryRead
from app.services.dashboard_service import get_device_status, get_energy_by_period, get_latest_telemetry, get_summary

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


@router.get("/energy/monthly", response_model=list[EnergyBucketRead])
def energy_monthly(
    organization_id: uuid.UUID | None = None,
    limit: int = Query(default=12, ge=1, le=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return get_energy_by_period(db=db, user=current_user, organization_id=organization_id, period="month", limit=limit)

