"""LTI 1.3 JWT validation using PyJWT.

Fetches the platform's JWKS, validates the launch id_token,
and checks the nonce matches what we stored during login.
"""

import jwt
from jwt import PyJWKClient

_jwks_clients: dict[str, PyJWKClient] = {}


def get_jwks_client(jwks_url: str) -> PyJWKClient:
    """Get or create a cached JWKS client for a platform."""
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_clients[jwks_url]


def validate_launch_token(
    id_token: str,
    jwks_url: str,
    client_id: str,
    issuer: str,
    nonce: str,
    deployment_id: str,
) -> dict:
    """Validate an LTI 1.3 launch JWT and return decoded claims.

    Checks: signature (via platform JWKS), exp, iat, aud, iss, nonce, deployment_id.
    """
    client = get_jwks_client(jwks_url)
    signing_key = client.get_signing_key_from_jwt(id_token)

    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
        issuer=issuer,
    )

    if claims.get("nonce") != nonce:
        raise jwt.InvalidTokenError("Nonce mismatch")

    claim_deployment_id = claims.get(
        "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
    )
    # Canvas may prefix deployment_id with an account ID (e.g. "221:dead3d8b...").
    # Accept if the claim equals our value or ends with ":<our_value>".
    if claim_deployment_id != deployment_id and not (
        claim_deployment_id and claim_deployment_id.endswith(f":{deployment_id}")
    ):
        raise jwt.InvalidTokenError(
            f"Deployment ID mismatch: expected {deployment_id}, got {claim_deployment_id}"
        )

    return claims
