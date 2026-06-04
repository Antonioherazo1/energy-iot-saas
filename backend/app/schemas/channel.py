import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    channel_number: int = Field(ge=1, le=4)
    name: str = Field(min_length=1, max_length=60)
    voltage: Decimal = Field(default=110, ge=0, le=999)


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    voltage: Decimal | None = Field(default=None, ge=0, le=999)
    is_active: bool | None = None


class ChannelRead(BaseModel):
    id: uuid.UUID
    device_id: uuid.UUID
    channel_number: int
    name: str
    voltage: Decimal
    is_active: bool

    model_config = {"from_attributes": True}
