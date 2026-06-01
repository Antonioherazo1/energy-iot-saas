import json
import logging

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.telemetry import TelemetryIn
from app.services.telemetry_service import InvalidDeviceKeyError, create_telemetry

logger = logging.getLogger(__name__)


class MQTTService:
    def __init__(self) -> None:
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def start(self) -> None:
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            client.subscribe(settings.mqtt_topic, qos=0)
            logger.info("MQTT connected and subscribed to %s", settings.mqtt_topic)
        else:
            logger.warning("MQTT connection failed: %s", reason_code)

    def _on_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
        try:
            device_code = message.topic.split("/")[1]
            payload = TelemetryIn(**json.loads(message.payload.decode("utf-8")))
        except (IndexError, json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
            logger.warning("Invalid MQTT telemetry payload: %s", exc)
            return

        with SessionLocal() as db:
            try:
                create_telemetry(db=db, device_code=device_code, payload=payload)
            except InvalidDeviceKeyError:
                logger.warning("Invalid MQTT device key for %s", device_code)


mqtt_service = MQTTService()
