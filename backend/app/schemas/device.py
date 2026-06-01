import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=80)


class DeviceRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    is_active: bool
    last_seen_at: datetime | None

    model_config = {"from_attributes": True}


class DeviceWithCredentials(DeviceRead):
    device_key: str

