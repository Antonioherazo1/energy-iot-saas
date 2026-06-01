import uuid

from pydantic import BaseModel

from app.models.organization import PlanType, UserRole


class OrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    plan: PlanType
    device_limit: int
    role: UserRole

