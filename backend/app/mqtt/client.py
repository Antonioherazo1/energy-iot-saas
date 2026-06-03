import json
import logging
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
        print(f"[MQTT] _on_connect called, reason_code={reason_code}", flush=True)
        if reason_code == 0:
            client.subscribe(settings.mqtt_topic, qos=0)
            client.subscribe(settings.esp32_topic, qos=0)
            print(f"[MQTT] Subscribed to {settings.mqtt_topic} and {settings.esp32_topic}", flush=True)
            logger.info("MQTT connected and subscribed")
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
        total_current = ch1 + ch2 + ch3 + ch4

        timestamp_str = payload_dict.get("timestamp", "")
        if timestamp_str and ":" in timestamp_str and len(timestamp_str) <= 8:
            parts = timestamp_str.split(":")
            now = datetime.now(timezone.utc)
            try:
                recorded_at = now.replace(
                    hour=int(parts[0]),
                    minute=int(parts[1]),
                    second=int(parts[2]) if len(parts) > 2 else 0,
                    microsecond=0,
                )
            except (ValueError, IndexError):
                recorded_at = now
        elif timestamp_str:
            try:
                recorded_at = datetime.fromisoformat(timestamp_str)
            except (ValueError, TypeError):
                recorded_at = datetime.now(timezone.utc)
        else:
            recorded_at = datetime.now(timezone.utc)

        voltage = settings.assumed_voltage

        telemetry = TelemetryIn(
            voltage=voltage,
            current=total_current,
            power=total_current * voltage,
            energy_kwh=None,
            frequency=None,
            power_factor=None,
            device_key=None,
            recorded_at=recorded_at,
        )
        return device_id, telemetry

    def _on_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
        try:
            payload_dict = json.loads(message.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning("Invalid MQTT payload: %s", exc)
            return

        topic = message.topic

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


mqtt_service = MQTTService()
