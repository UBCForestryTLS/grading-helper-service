from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    table_name: str = "GradingTable"
    bucket_name: str = "GradingBucket"
    stage: str = "local"
    aws_region: str = "us-west-2"
    powertools_service_name: str = "grading-helper"

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
