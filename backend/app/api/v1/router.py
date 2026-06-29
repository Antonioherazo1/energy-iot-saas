from fastapi import APIRouter

from app.api.v1.endpoints import auth, dashboard, devices, esp32, firmware, health, organizations, settings, telemetry, ws

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["telemetry"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(esp32.router, prefix="/esp32", tags=["esp32"])
api_router.include_router(firmware.router, prefix="/firmware", tags=["firmware"])
api_router.include_router(ws.router, prefix="/ws", tags=["websockets"])
