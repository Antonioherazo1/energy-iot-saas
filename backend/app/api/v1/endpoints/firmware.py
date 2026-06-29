import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.firmware import Firmware
from app.core.config import settings
from app.mqtt.client import mqtt_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["firmware"])


@router.get("/versions")
async def list_firmware(user=Depends(get_current_user), db: Session = Depends(get_db)):
    result = db.execute(select(Firmware).order_by(Firmware.created_at.desc()))
    return result.scalars().all()


@router.post("/upload")
async def upload_firmware(
    version: str = Form(...),
    file: UploadFile = File(...),
    notes: str = Form(""),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    os.makedirs(settings.firmware_dir, exist_ok=True)

    filename = f"medidor_{version}.bin"
    filepath = os.path.join(settings.firmware_dir, filename)

    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()

    with open(filepath, "wb") as f:
        f.write(content)

    fw = Firmware(
        version=version,
        filename=filename,
        filepath=filepath,
        file_size=len(content),
        checksum=checksum,
        notes=notes,
    )
    db.add(fw)
    db.commit()
    db.refresh(fw)

    download_url = f"{settings.firmware_base_url}/{filename}"
    return {"ok": True, "firmware": {"id": str(fw.id), "version": fw.version, "filename": fw.filename, "file_size": fw.file_size, "checksum": fw.checksum, "url": download_url}}


@router.post("/ota/{device_id}")
async def trigger_ota(
    device_id: str,
    firmware_id: str = Form(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fw = db.get(Firmware, UUID(firmware_id))
    if not fw:
        raise HTTPException(status_code=404, detail="Firmware no encontrado")

    download_url = f"{settings.firmware_base_url}/{fw.filename}"
    payload = json.dumps({"cmd": "ota", "url": download_url})
    mqtt_service.publish_command(device_id, payload)
    return {"ok": True, "device_id": device_id, "firmware_version": fw.version, "url": download_url}


@router.post("/ota/all")
async def trigger_ota_all(
    firmware_id: str = Form(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.device import Device

    fw = db.get(Firmware, UUID(firmware_id))
    if not fw:
        raise HTTPException(status_code=404, detail="Firmware no encontrado")

    result = db.execute(select(Device))
    devices = result.scalars().all()
    download_url = f"{settings.firmware_base_url}/{fw.filename}"
    payload = json.dumps({"cmd": "ota", "url": download_url})

    sent = []
    for dev in devices:
        try:
            mqtt_service.publish_command(dev.device_id, payload)
            sent.append(dev.device_id)
        except Exception as e:
            logger.error("Error sending OTA to %s: %s", dev.device_id, e)

    return {"ok": True, "sent": len(sent), "total": len(devices), "firmware_version": fw.version}
