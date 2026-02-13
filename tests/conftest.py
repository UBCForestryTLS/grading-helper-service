"""Shared test fixtures for the grading helper service."""

import os

import boto3
import pytest
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
