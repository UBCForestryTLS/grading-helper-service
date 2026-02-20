from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    table_name: str = "GradingTable"
    bucket_name: str = "GradingBucket"
    stage: str = "local"
    aws_region: str = "ca-central-1"
    powertools_service_name: str = "grading-helper"

    # LTI 1.3 configuration
    base_url: str = ""  # e.g. https://xxx.execute-api.ca-central-1.amazonaws.com/dev
    lti_iss: str = ""  # Platform issuer URL
    lti_client_id: str = ""
    lti_deployment_id: str = ""
    lti_auth_login_url: str = ""  # Platform OIDC auth endpoint
    lti_auth_token_url: str = ""  # Platform OAuth2 token endpoint
    lti_key_set_url: str = ""  # Platform JWKS URL
    lti_private_key: str = ""  # PEM private key (direct or via SSM)
    lti_private_key_ssm_param: str = "/grading-helper/lti-private-key"

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
