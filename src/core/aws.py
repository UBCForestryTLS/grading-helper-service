import boto3

from src.core.config import get_settings


def get_dynamodb_resource():
    settings = get_settings()
    return boto3.resource("dynamodb", region_name=settings.aws_region)


def get_dynamodb_table():
    settings = get_settings()
    resource = get_dynamodb_resource()
    return resource.Table(settings.table_name)


def get_s3_client():
    settings = get_settings()
    return boto3.client("s3", region_name=settings.aws_region)
