from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.mqtt.client import mqtt_service
from app.websockets.manager import websocket_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[lifespan] Setting up WebSocket loop...", flush=True)
    websocket_manager.set_loop(asyncio.get_running_loop())
    print(f"[lifespan] MQTT enabled: {settings.mqtt_enabled}", flush=True)
    if settings.mqtt_enabled:
        print("[lifespan] Starting MQTT service...", flush=True)
        mqtt_service.start()
        print("[lifespan] MQTT service started", flush=True)
    yield
    if settings.mqtt_enabled:
        mqtt_service.stop()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
