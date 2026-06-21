import json
import logging
import threading
from datetime import datetime, timezone

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
        self._device_configs: dict[str, dict] = {}
        self._last_responses: dict[str, dict] = {}
        self._lock = threading.Lock()

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
            client.subscribe(settings.esp32_topic, qos=0)
            client.subscribe("energia/respuesta/+", qos=0)
            logger.info(
                "MQTT connected. Subscribed to %s, %s, energia/respuesta/+",
                settings.mqtt_topic,
                settings.esp32_topic,
            )
        else:
            logger.warning("MQTT connection failed: %s", reason_code)

    def _parse_esp32_payload(self, payload_dict: dict) -> tuple[str, TelemetryIn] | None:
        device_id = payload_dict.get("device_id", "")
        if not device_id:
            return None

        ch1 = float(payload_dict.get("ch1", 0))
        ch2 = float(payload_dict.get("ch2", 0))
        ch3 = float(payload_dict.get("ch3", 0))
        ch4 = float(payload_dict.get("ch4", 0))

        timestamp_str = payload_dict.get("timestamp", "")
        if timestamp_str and ":" in timestamp_str and len(timestamp_str) <= 8:
            now = datetime.now(timezone.utc)
            recorded_at = now
        elif timestamp_str:
            try:
                recorded_at = datetime.fromisoformat(timestamp_str)
                if recorded_at.tzinfo is None:
                    recorded_at = recorded_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                recorded_at = datetime.now(timezone.utc)
        else:
            recorded_at = datetime.now(timezone.utc)

        telemetry = TelemetryIn(
            current=ch1 + ch2 + ch3 + ch4,
            ch1=ch1,
            ch2=ch2,
            ch3=ch3,
            ch4=ch4,
            device_key=None,
            recorded_at=recorded_at,
        )
        return device_id, telemetry

    def _on_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
        topic = message.topic

        try:
            payload_dict = json.loads(message.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Invalid MQTT payload on %s: %s", topic, exc)
            return

        if topic.startswith("energia/respuesta/"):
            self._handle_response(payload_dict, topic)
            return

        if topic == settings.esp32_topic:
            result = self._parse_esp32_payload(payload_dict)
            if result is None:
                return
            device_code, payload = result
        else:
            try:
                device_code = topic.split("/")[1]
                payload = TelemetryIn(**payload_dict)
            except (IndexError, ValidationError) as exc:
                logger.warning("Invalid MQTT message on %s: %s", topic, exc)
                return

        with SessionLocal() as db:
            try:
                create_telemetry(db=db, device_code=device_code, payload=payload)
            except InvalidDeviceKeyError:
                logger.warning("Invalid MQTT device key for %s", device_code)

    def _handle_response(self, payload_dict: dict, topic: str) -> None:
        device_id = topic.split("/")[-1]
        cmd = payload_dict.get("cmd", "")
        with self._lock:
            self._last_responses[device_id] = {
                "response": payload_dict,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        if cmd == "status":
            settings_data = payload_dict.get("settings", {})
            if settings_data:
                with self._lock:
                    self._device_configs[device_id] = {
                        "settings": settings_data,
                        "uptime": payload_dict.get("uptime"),
                        "rssi": payload_dict.get("rssi"),
                        "buffer": payload_dict.get("buffer"),
                        "firmware": payload_dict.get("firmware"),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                logger.info("Config cached for device %s", device_id)

    def publish_command(self, device_id: str, payload: str) -> None:
        self.client.publish(f"energia/comando/{device_id}", payload, qos=1)

    def get_device_config(self, device_id: str) -> dict | None:
        with self._lock:
            return self._device_configs.get(device_id)

    def get_last_response(self, device_id: str) -> dict | None:
        with self._lock:
            return self._last_responses.get(device_id)

    def request_status(self, device_id: str) -> None:
        self.publish_command(device_id, '{"cmd":"status"}')


mqtt_service = MQTTService()
