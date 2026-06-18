from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Telemetry Service"
    PORT: int = 8003
    DATABASE_URL: str
    
    MQTT_BROKER: str = "host.docker.internal"
    MQTT_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None

    class Config:
        env_file = ".env"

settings = Settings()
