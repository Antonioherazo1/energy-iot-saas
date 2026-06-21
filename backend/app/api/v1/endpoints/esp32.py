import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.mqtt.client import mqtt_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/esp32", tags=["esp32"])


class CommandPayload(BaseModel):
    cmd: str
    canal: int | None = None
    valor: float | None = None
    habilitado: bool | None = None


@router.get("/{device_id}/status")
async def get_device_status(device_id: str, user=Depends(get_current_user)):
    config = mqtt_service.get_device_config(device_id)
    if config is None:
        mqtt_service.request_status(device_id)
        return {"cached": False, "data": None}
    return {"cached": True, "data": config}


@router.post("/{device_id}/command")
async def send_command(device_id: str, payload: CommandPayload, user=Depends(get_current_user)):
    cmd_dict = {"cmd": payload.cmd}
    if payload.canal is not None:
        cmd_dict["canal"] = payload.canal
    if payload.valor is not None:
        cmd_dict["valor"] = payload.valor
    if payload.habilitado is not None:
        cmd_dict["habilitado"] = payload.habilitado

    import json
    mqtt_service.publish_command(device_id, json.dumps(cmd_dict))
    return {"ok": True, "command": cmd_dict}


@router.post("/{device_id}/command/admin")
async def send_admin_command(
    device_id: str,
    payload: CommandPayload,
    x_admin_password: str = Header(alias="X-Admin-Password"),
    user=Depends(get_current_user),
):
    if x_admin_password != settings.admin_password:
        raise HTTPException(status_code=403, detail="Contrasena de administrador incorrecta")

    cmd_dict = {"cmd": payload.cmd}
    if payload.canal is not None:
        cmd_dict["canal"] = payload.canal
    if payload.valor is not None:
        cmd_dict["valor"] = payload.valor
    if payload.habilitado is not None:
        cmd_dict["habilitado"] = payload.habilitado

    import json
    mqtt_service.publish_command(device_id, json.dumps(cmd_dict))
    return {"ok": True, "command": cmd_dict, "admin": True}
