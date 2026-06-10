from pydantic import BaseModel


class SettingUpdate(BaseModel):
    value: str
