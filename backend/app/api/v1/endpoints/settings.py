from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.organization import OrganizationMember
from app.models.setting import OrganizationSetting
from app.models.user import User
from app.schemas.setting import SettingUpdate

router = APIRouter()


@router.get("/kwh-rate")
def get_kwh_rate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    setting = db.scalar(
        select(OrganizationSetting).where(
            OrganizationSetting.organization_id == membership.organization_id,
            OrganizationSetting.key == "kwh_rate",
        )
    )
    return {"value": setting.value if setting else "800"}


@router.put("/kwh-rate")
def update_kwh_rate(
    payload: SettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    setting = db.scalar(
        select(OrganizationSetting).where(
            OrganizationSetting.organization_id == membership.organization_id,
            OrganizationSetting.key == "kwh_rate",
        )
    )
    if setting:
        setting.value = payload.value
    else:
        setting = OrganizationSetting(
            organization_id=membership.organization_id, key="kwh_rate", value=payload.value
        )
        db.add(setting)
    db.commit()
    return {"value": payload.value}


@router.get("/{key}")
def get_setting(
    key: str,
    default: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    setting = db.scalar(
        select(OrganizationSetting).where(
            OrganizationSetting.organization_id == membership.organization_id,
            OrganizationSetting.key == key,
        )
    )
    return {"value": setting.value if setting else default}


@router.put("/{key}")
def update_setting(
    key: str,
    payload: SettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = db.scalar(
        select(OrganizationMember).where(OrganizationMember.user_id == current_user.id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    setting = db.scalar(
        select(OrganizationSetting).where(
            OrganizationSetting.organization_id == membership.organization_id,
            OrganizationSetting.key == key,
        )
    )
    if setting:
        setting.value = payload.value
    else:
        setting = OrganizationSetting(
            organization_id=membership.organization_id, key=key, value=payload.value
        )
        db.add(setting)
    db.commit()
    return {"value": payload.value}
