import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device import Device
from app.models.organization import OrganizationMember
from app.models.telemetry import Telemetry
from app.models.user import User
from app.schemas.telemetry import TelemetryIn, TelemetryRead
from app.services.telemetry_service import InvalidDeviceKeyError, create_telemetry

router = APIRouter()


@router.get("/{device_id}", response_model=list[TelemetryRead])
def list_device_telemetry(
    device_id: uuid.UUID,
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Telemetry]:
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == device.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to device")

    safe_limit = max(1, min(limit, 1000))
    return list(
        db.scalars(
            select(Telemetry)
            .where(Telemetry.device_id == device_id)
            .order_by(Telemetry.recorded_at.desc())
            .limit(safe_limit)
        )
    )


@router.post("/{device_code}", response_model=TelemetryRead, status_code=status.HTTP_201_CREATED)
def ingest_http_telemetry(device_code: str, payload: TelemetryIn, db: Session = Depends(get_db)) -> Telemetry:
    try:
        telemetry = create_telemetry(db=db, device_code=device_code, payload=payload)
    except InvalidDeviceKeyError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device key")
    if telemetry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return telemetry
