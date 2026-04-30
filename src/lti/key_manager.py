"""RSA key management for LTI 1.3 JWT signing and JWKS endpoint.

Note on key rotation: both `get_private_key` and `get_public_jwk` are cached
with `lru_cache`, so the key is fetched once per process (Lambda cold start).
If the key is rotated in SSM, running Lambda containers will keep using the
old value until they are recycled — redeploy or otherwise restart the
service to pick up a new key.
"""

import functools
import json

import boto3
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from jwt.algorithms import RSAAlgorithm

from src.core.config import get_settings


@functools.lru_cache
def get_private_key() -> str:
    """Load private key PEM from env var or SSM Parameter Store."""
    settings = get_settings()
    if settings.lti_private_key:
        return settings.lti_private_key

    ssm = boto3.client("ssm", region_name=settings.aws_region)
    response = ssm.get_parameter(
        Name=settings.lti_private_key_ssm_param,
        WithDecryption=True,
    )
    return response["Parameter"]["Value"]


@functools.lru_cache
def get_public_jwk() -> dict:
    """Derive the public JWK from the private key (for the JWKS endpoint)."""
    private_key = load_pem_private_key(get_private_key().encode(), password=None)
    public_key = private_key.public_key()
    jwk = json.loads(RSAAlgorithm.to_jwk(public_key))
    jwk["alg"] = "RS256"
    jwk["use"] = "sig"
    jwk["kid"] = "grading-helper-1"
    return jwk
