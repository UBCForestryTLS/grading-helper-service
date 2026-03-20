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

    # Bedrock configuration
    bedrock_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

    # Canvas API OAuth2 (API Developer Key — for REST API access on behalf of instructor)
    api_client_id: str = ""  # Canvas API Developer Key client_id (244490000000000213)
    api_client_secret: str = (
        ""  # Canvas API Developer Key client_secret (pending from William)
    )
    api_canvas_url: str = (
        ""  # Canvas instance base URL (e.g. https://ubcstaging.instructure.com)
    )

    model_config = {"env_prefix": "", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()
