from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    monolith_url: str = 'http://monolith:8080'
    movies_service_url: str = 'http://movies-service:8081'
    events_service_url: str = 'http://events-service:8082'
    gradual_migration: bool = True
    movies_migration_percent: int = Field(default=50, ge=0, le=100)
    upstream_timeout: float = Field(default=10, gt=0)
