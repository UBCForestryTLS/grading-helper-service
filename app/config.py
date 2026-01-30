"""Application configuration using Pydantic settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Grading Helper Service"
    dev_mode: bool = False

    # Database
    database_url: str = "sqlite:///./grading.db"

    # Canvas API (required in dev mode)
    canvas_base_url: str = ""
    canvas_api_token: str = ""

    # AWS Bedrock
    aws_region: str = "us-west-2"


# Global settings instance
settings = Settings()
