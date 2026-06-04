import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.channel import DeviceChannel
from app.models.device import Device
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.channel import ChannelCreate, ChannelRead, ChannelUpdate
from app.schemas.device import DeviceCreate, DeviceRead, DeviceWithCredentials
from app.services.device_credentials import generate_device_key, hash_device_key

router = APIRouter()


@router.get("", response_model=list[DeviceRead])
def list_devices(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Device]:
    organization_ids = [membership.organization_id for membership in current_user.memberships]
    if not organization_ids:
        return []
    return list(db.scalars(select(Device).where(Device.organization_id.in_(organization_ids)).order_by(Device.name)))


@router.post("/link", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
def link_device(payload: DeviceCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Device:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == payload.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to organization")

    organization = db.get(Organization, payload.organization_id)
    device_count = db.scalar(select(func.count(Device.id)).where(Device.organization_id == payload.organization_id)) or 0
    if organization and device_count >= organization.device_limit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device limit reached for current plan")

    device = Device(
        organization_id=payload.organization_id,
        name=payload.name,
        code=payload.code,
        device_key_hash=None,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.post("", response_model=DeviceWithCredentials, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == payload.organization_id,
            OrganizationMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to organization")

    organization = db.get(Organization, payload.organization_id)
    device_count = db.scalar(select(func.count(Device.id)).where(Device.organization_id == payload.organization_id)) or 0
    if organization and device_count >= organization.device_limit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device limit reached for current plan")

    device_key = generate_device_key()
    device = Device(
        organization_id=payload.organization_id,
        name=payload.name,
        code=payload.code,
        device_key_hash=hash_device_key(device_key),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {
        "id": device.id,
        "organization_id": device.organization_id,
        "name": device.name,
        "code": device.code,
        "is_active": device.is_active,
        "last_seen_at": device.last_seen_at,
        "device_key": device_key,
    }


@router.post("/{device_id}/credentials", response_model=DeviceWithCredentials)
def rotate_device_credentials(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
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

    device_key = generate_device_key()
    device.device_key_hash = hash_device_key(device_key)
    db.commit()
    db.refresh(device)

    return {
        "id": device.id,
        "organization_id": device.organization_id,
        "name": device.name,
        "code": device.code,
        "is_active": device.is_active,
        "last_seen_at": device.last_seen_at,
        "device_key": device_key,
    }


def _get_device_with_access(device_id: uuid.UUID, current_user: User, db: Session) -> Device:
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
    return device


@router.get("/{device_id}/channels", response_model=list[ChannelRead])
def list_channels(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeviceChannel]:
    device = _get_device_with_access(device_id, current_user, db)
    return list(db.scalars(select(DeviceChannel).where(DeviceChannel.device_id == device.id).order_by(DeviceChannel.channel_number)))


@router.put("/{device_id}/channels/{channel_number}", response_model=ChannelRead)
def update_channel(
    device_id: uuid.UUID,
    channel_number: int,
    payload: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DeviceChannel:
    device = _get_device_with_access(device_id, current_user, db)
    channel = db.scalar(
        select(DeviceChannel).where(
            DeviceChannel.device_id == device.id,
            DeviceChannel.channel_number == channel_number,
        )
    )
    if channel is None:
        channel = DeviceChannel(
            device_id=device.id,
            channel_number=channel_number,
            name=payload.name or f"Canal {channel_number}",
            voltage=payload.voltage or settings.assumed_voltage,
            is_active=payload.is_active if payload.is_active is not None else True,
        )
        db.add(channel)
    else:
        if payload.name is not None:
            channel.name = payload.name
        if payload.voltage is not None:
            channel.voltage = payload.voltage
        if payload.is_active is not None:
            channel.is_active = payload.is_active
    db.commit()
    db.refresh(channel)
    return channel


@router.post("/{device_id}/channels/setup", response_model=list[ChannelRead])
def setup_channels(
    device_id: uuid.UUID,
    channels: list[ChannelCreate],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DeviceChannel]:
    device = _get_device_with_access(device_id, current_user, db)
    existing = list(db.scalars(select(DeviceChannel).where(DeviceChannel.device_id == device.id)))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Channels already configured for this device")

    created = []
    for ch in channels:
        channel = DeviceChannel(
            device_id=device.id,
            channel_number=ch.channel_number,
            name=ch.name,
            voltage=ch.voltage,
            is_active=True,
        )
        db.add(channel)
        created.append(channel)
    db.commit()
    for ch in created:
        db.refresh(ch)
    return created


@router.delete("/{device_id}")
def delete_device(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    device = _get_device_with_access(device_id, current_user, db)
    db.delete(device)
    db.commit()
    return {"ok": True}
