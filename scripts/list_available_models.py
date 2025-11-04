#!/usr/bin/env python3
"""
List all available models in your AWS Bedrock account.
This helps identify the correct model IDs to use.
"""

import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    """List all foundation models available in Bedrock."""

    print("Fetching available models from AWS Bedrock...")
    print("=" * 70)

    # Get region from environment
    region = os.getenv("AWS_REGION", "ca-central-1")
    print(f"Region: {region}\n")

    # Use bedrock (not bedrock-runtime) for listing models
    # Note: boto3 automatically handles AWS_BEARER_TOKEN_BEDROCK if set
    bedrock_client = boto3.client(service_name="bedrock", region_name=region)

    try:
        response = bedrock_client.list_foundation_models()
        models = response.get("modelSummaries", [])

        print(f"\nFound {len(models)} models\n")

        # Filter for Claude models specifically
        claude_models = [m for m in models if "claude" in m.get("modelId", "").lower()]

        if claude_models:
            print("CLAUDE MODELS AVAILABLE:")
            print("=" * 70)
            for model in claude_models:
                model_id = model.get("modelId", "N/A")
                model_name = model.get("modelName", "N/A")
                provider = model.get("providerName", "N/A")

                # Check if model supports text generation
                input_modalities = model.get("inputModalities", [])
                output_modalities = model.get("outputModalities", [])

                print(f"\nModel ID: {model_id}")
                print(f"Name: {model_name}")
                print(f"Provider: {provider}")
                print(f"Input: {', '.join(input_modalities)}")
                print(f"Output: {', '.join(output_modalities)}")
                print("-" * 70)
        else:
            print("No Claude models found.")

        # Show all models for reference
        print("\n\nALL AVAILABLE MODELS:")
        print("=" * 70)
        for model in models:
            print(f"• {model.get('modelId')} - {model.get('modelName')}")

    except ClientError as e:
        print(f"Error fetching models: {e}")
        raise


if __name__ == "__main__":
    main()
