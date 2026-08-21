import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import select, func, text

from app.api.deps import get_current_user
from app.db.session import SessionLocal
from app.models.device import Device
from app.models.raw_telemetry import RawTelemetry
from app.mqtt.client import mqtt_service
from app.services.mqtt_cache import get_last_messages
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["esp32"])


class CommandPayload(BaseModel):
    cmd: str
    canal: int | None = None
    valor: float | None = None
    habilitado: bool | None = None


@router.get("/last-messages")
async def last_messages(user=Depends(get_current_user)):
    return get_last_messages()


@router.get("/diagnostic")
async def diagnostic(user=Depends(get_current_user)):
    return {
        "configs": mqtt_service.get_all_configs(),
        "responses": mqtt_service.get_all_responses(),
    }


@router.get("/{device_id}/status")
async def get_device_status(device_id: str, user=Depends(get_current_user)):
    import json
    config = mqtt_service.get_device_config(device_id)
    if config is not None:
        updated = config.get("updated_at")
        if updated:
            from datetime import datetime, timezone
            updated_dt = datetime.fromisoformat(updated)
            age = (datetime.now(timezone.utc) - updated_dt).total_seconds()
            if age > 60:
                config = None
    if config is None:
        mqtt_service.request_status(device_id)
        return {"cached": False, "data": None}
    return {"cached": True, "data": config}


@router.get("/{device_id}/last-response")
async def get_last_response(device_id: str, user=Depends(get_current_user)):
    resp = mqtt_service.get_last_response(device_id)
    if resp is None:
        return {"response": None}
    return resp


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
    mqtt_service.publish_command(device_id, json.dumps(cmd_dict, separators=(",", ":")))
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
    mqtt_service.publish_command(device_id, json.dumps(cmd_dict, separators=(",", ":")))
    return {"ok": True, "command": cmd_dict, "admin": True}


@router.get("/{device_id}/telemetry-health")
async def get_telemetry_health(device_id: str, hours: int = 24, user=Depends(get_current_user)):
    with SessionLocal() as db:
        device = db.scalar(select(Device).where(Device.id == device_id))
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")

        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        rows = db.execute(
            select(RawTelemetry.recorded_at)
            .where(RawTelemetry.device_id == device.id, RawTelemetry.recorded_at >= since)
            .order_by(RawTelemetry.recorded_at.asc())
        ).scalars().all()

        if len(rows) < 2:
            return {
                "device_id": device_id,
                "hours": hours,
                "total_records": len(rows),
                "gaps": [],
                "buffer_events": [],
                "avg_interval_sec": None,
            }

        def _utc(ts: datetime) -> datetime:
            return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)

        gaps = []
        buffer_events = []
        intervals = []

        for i in range(1, len(rows)):
            prev_ts = _utc(rows[i - 1])
            curr_ts = _utc(rows[i])
            delta = (curr_ts - prev_ts).total_seconds()

            intervals.append(delta)

            if delta > 300:
                recovered = 0
                j = i
                while j < len(rows) and recovered < 500:
                    if j > i and (_utc(rows[j]) - _utc(rows[j - 1])).total_seconds() > 15:
                        break
                    recovered += 1
                    j += 1
                gaps.append({
                    "from": prev_ts.isoformat(),
                    "to": curr_ts.isoformat(),
                    "duration_sec": int(delta),
                    "recovered": recovered,
                })

            if i >= 3:
                avg_before = sum(intervals[max(0, i - 10):i]) / min(10, i)
                if delta < avg_before * 0.3 and delta < 60 and avg_before > 10:
                    buffer_events.append({
                        "timestamp": curr_ts.isoformat(),
                        "interval_sec": round(delta, 1),
                        "normal_interval_sec": round(avg_before, 1),
                    })

        avg_interval = sum(intervals) / len(intervals) if intervals else None

        return {
            "device_id": device_id,
            "hours": hours,
            "total_records": len(rows),
            "gaps": gaps[-20:],
            "buffer_events": buffer_events[-50:],
            "avg_interval_sec": round(avg_interval, 1) if avg_interval else None,
        }
