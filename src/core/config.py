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

    # Mock/Simulation mode (default: true for demo safety - no actual drone commands)
    mock_mode: bool = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency for FastAPI to get settings instance."""
    return settings
