from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.organization import OrganizationRead

router = APIRouter()


@router.get("", response_model=list[OrganizationRead])
def list_organizations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(
            Organization.id,
            Organization.name,
            Organization.plan,
            Organization.device_limit,
            OrganizationMember.role,
        )
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == current_user.id)
        .order_by(Organization.name)
    )
    return [dict(row._mapping) for row in rows]

