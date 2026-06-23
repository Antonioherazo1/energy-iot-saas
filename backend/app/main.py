import logging
import threading
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.mqtt.client import mqtt_service
from app.services.telemetry_service import aggregate_raw_telemetry, cleanup_raw_telemetry
from app.websockets.manager import websocket_manager

logger = logging.getLogger(__name__)

_AGGREGATION_INTERVAL = 60
_CLEANUP_INTERVAL = 3600


def _run_aggregation_loop():
    logger.info("Iniciando loop de agregación raw_telemetry (cada %ss)", _AGGREGATION_INTERVAL)
    import time
    last_agg = 0.0
    last_cleanup = 0.0
    while True:
        time.sleep(10)
        now = time.monotonic()
        try:
            if now - last_agg >= _AGGREGATION_INTERVAL:
                with SessionLocal() as db:
                    n = aggregate_raw_telemetry(db)
                    if n:
                        logger.info("Agregados %d registros raw a telemetry", n)
                last_agg = now
        except Exception:
            logger.exception("Error en agregación raw")
        try:
            if now - last_cleanup >= _CLEANUP_INTERVAL:
                with SessionLocal() as db:
                    n = cleanup_raw_telemetry(db)
                    if n:
                        logger.info("Limpiados %d registros raw antiguos", n)
                last_cleanup = now
        except Exception:
            logger.exception("Error en limpieza raw")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando WebSocket loop...")
    websocket_manager.set_loop(asyncio.get_running_loop())
    logger.info("MQTT habilitado: %s", settings.mqtt_enabled)
    if settings.mqtt_enabled:
        logger.info("Iniciando servicio MQTT...")
        mqtt_service.start()
        logger.info("Servicio MQTT iniciado")
    agg_thread = threading.Thread(target=_run_aggregation_loop, daemon=True)
    agg_thread.start()
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
