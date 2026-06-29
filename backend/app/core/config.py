from functools import cached_property

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Energy IoT SaaS"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str | list[str] = "http://localhost:5173"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "energy_iot"
    postgres_user: str = "energy_iot"
    postgres_password: str = "change_me"

    jwt_secret_key: str = "change_me_generate_64_chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    refresh_token_expire_days: int = 30

    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_topic: str = "devices/+/telemetry"
    assumed_voltage: int = 110
    esp32_topic: str = "energia/datos"
    admin_password: str = "admin123"
    firmware_dir: str = "/app/firmware"
    firmware_base_url: str = "http://localhost:8000/firmware"

    db_pool_size: int = 5
    db_max_overflow: int = 5

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def cors_origins(self) -> list[str]:
        if isinstance(self.backend_cors_origins, str):
            return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]
        return self.backend_cors_origins

    @cached_property
    def database_url(self) -> str:
        return (
            "postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
