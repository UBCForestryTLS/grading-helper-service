"""Shared test fixtures for the grading helper service."""

import os

import boto3
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from moto import mock_aws


@pytest.fixture
def aws_credentials():
    """Set dummy AWS credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "ca-central-1"


@pytest.fixture
def dynamodb_table(aws_credentials):
    """Create a mocked DynamoDB table matching template.yaml."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ca-central-1")
        table = dynamodb.create_table(
            TableName="GradingTable",
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="GradingTable")
        yield table


@pytest.fixture
def sample_canvas_data():
    """Minimal valid Canvas quiz export with 1 short-answer question and 2 submissions."""
    return {
        "short_answer_question": [
            {
                "id": 101,
                "quiz_id": 50,
                "question_name": "Q1",
                "question_type": "short_answer_question",
                "question_text": "<p>What is photosynthesis?</p>",
                "points_possible": 5.0,
                "answers": [
                    {
                        "id": 1,
                        "text": "The process by which plants convert light to energy",
                        "weight": 100,
                        "comments": "",
                    },
                    {
                        "id": 2,
                        "text": "Converting sunlight into food",
                        "weight": 100,
                        "comments": "",
                    },
                ],
                "submissions": [
                    {"answer": "Plants use sunlight to make food", "points": 5.0},
                    {"answer": "I don't know", "points": 0.0},
                ],
            }
        ],
        "fill_in_multiple_blanks_question": [],
    }


@pytest.fixture
def lti_env_vars(aws_credentials):
    """Set LTI environment variables with a test RSA key pair."""
    from src.core.config import get_settings
    from src.lti.key_manager import get_private_key, get_public_jwk
    from src.auth.session import _get_public_key

    get_settings.cache_clear()
    get_private_key.cache_clear()
    get_public_jwk.cache_clear()
    _get_public_key.cache_clear()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()

    os.environ["BASE_URL"] = "https://test.execute-api.ca-central-1.amazonaws.com/dev"
    os.environ["LTI_ISS"] = "https://canvas.test.instructure.com"
    os.environ["LTI_CLIENT_ID"] = "10000000000001"
    os.environ["LTI_DEPLOYMENT_ID"] = "1:test-deployment"
    os.environ["LTI_AUTH_LOGIN_URL"] = (
        "https://canvas.test.instructure.com/api/lti/authorize_redirect"
    )
    os.environ["LTI_AUTH_TOKEN_URL"] = (
        "https://canvas.test.instructure.com/login/oauth2/token"
    )
    os.environ["LTI_KEY_SET_URL"] = (
        "https://canvas.test.instructure.com/api/lti/security/jwks"
    )
    os.environ["LTI_PRIVATE_KEY"] = pem

    yield

    for key in [
        "BASE_URL",
        "LTI_ISS",
        "LTI_CLIENT_ID",
        "LTI_DEPLOYMENT_ID",
        "LTI_AUTH_LOGIN_URL",
        "LTI_AUTH_TOKEN_URL",
        "LTI_KEY_SET_URL",
        "LTI_PRIVATE_KEY",
    ]:
        os.environ.pop(key, None)
    get_settings.cache_clear()
    get_private_key.cache_clear()
    get_public_jwk.cache_clear()
    _get_public_key.cache_clear()


@pytest.fixture
def session_token(lti_env_vars):
    """Create a valid RS256 session token for course C100."""
    from src.auth.session import create_session_token

    return create_session_token(
        launch_id="test-launch-id",
        course_id="C100",
        canvas_user_id="test-user-123",
    )
