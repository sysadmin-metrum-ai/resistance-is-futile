"""Configuration module using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # PostgREST configuration
    postgrest_url: str = "http://localhost:3000"
    postgrest_api_key: str = ""

    # Redis configuration
    redis_url: str = "redis://localhost:6379"

    # API authentication
    api_key: str = ""

    # Camera configuration
    image_storage_path: str = "./captures"
    image_quality: int = 85
    camera_backend: str = "placeholder"
    camera_max_concurrent_streams: int = 3
    camera_connect_timeout_seconds: float = 3.0
    camera_read_timeout_seconds: float = 10.0
    camera_placeholder_stream_base: str = "placeholder://stream"

    # Mock/Simulation mode (default: true for demo safety - no actual drone commands)
    mock_mode: bool = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency for FastAPI to get settings instance."""
    return settings
