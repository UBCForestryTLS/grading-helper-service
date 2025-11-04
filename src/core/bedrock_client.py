"""AWS Bedrock client wrapper for invoking Claude models."""

import json
import logging
import os
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockClient:
    """
    Wrapper for AWS Bedrock API to invoke Claude models.

    Handles model invocation, token tracking, and cost calculation.
    """

    def __init__(self, region_name: str | None = None):
        """
        Initialize the Bedrock client.

        Args:
            region_name: AWS region (defaults to AWS_REGION env var or us-east-1)
        """
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")

        # Initialize boto3 client for bedrock-runtime
        # Note: boto3 automatically handles AWS_BEARER_TOKEN_BEDROCK if set
        self.client = boto3.client(service_name="bedrock-runtime", region_name=self.region_name)

        logger.info(f"Initialized BedrockClient for region: {self.region_name}")

    def invoke_model(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        max_tokens: int = 1000,
        temperature: float = 0.0,
        top_p: float = 1.0,
    ) -> dict[str, Any]:
        """
        Invoke a Claude model via AWS Bedrock.

        Args:
            model_id: The Bedrock model ID (e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0")
            messages: List of message dicts with 'role' and 'content' keys
            system_prompt: Optional system prompt to set model behavior
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)
            top_p: Nucleus sampling parameter

        Returns:
            Dict containing:
                - response_text: The generated text
                - input_tokens: Number of input tokens used
                - output_tokens: Number of output tokens generated
                - model_id: The model used
                - timestamp: ISO timestamp of the request

        Raises:
            ClientError: If the API request fails
            ValueError: If the response structure is invalid or unexpected
            KeyError: If expected fields are missing from response
            IndexError: If response arrays are unexpectedly empty
        """
        # Prepare the request body following Anthropic's Messages API format
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        # Add system prompt if provided
        if system_prompt:
            request_body["system"] = system_prompt

        try:
            # Invoke the model
            logger.debug(f"Invoking model {model_id} with {len(messages)} messages")

            response = self.client.invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body),
            )

            # Parse the response
            response_body = json.loads(response["body"].read())

            # Validate response structure
            if "content" not in response_body:
                raise ValueError(
                    f"Invalid response from model {model_id}: missing 'content' field. "
                    f"Response: {response_body}"
                )

            if not response_body["content"] or len(response_body["content"]) == 0:
                raise ValueError(
                    f"Invalid response from model {model_id}: 'content' array is empty. "
                    f"Response: {response_body}"
                )

            if "text" not in response_body["content"][0]:
                raise ValueError(
                    f"Invalid response from model {model_id}: missing 'text' field in content. "
                    f"Response: {response_body}"
                )

            # Extract the generated text
            response_text = response_body["content"][0]["text"]

            # Extract token usage
            usage = response_body.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            logger.info(
                f"Model invocation successful. "
                f"Input tokens: {input_tokens}, Output tokens: {output_tokens}"
            )

            return {
                "response_text": response_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model_id": model_id,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except ClientError as e:
            logger.error(f"Failed to invoke model {model_id}: {e}")
            raise
        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Failed to parse response from model {model_id}: {e}")
            raise

    def calculate_cost(
        self, model_id: str, input_tokens: int, output_tokens: int, cost_config: dict[str, float]
    ) -> float:
        """
        Calculate the cost of a model invocation.

        Args:
            model_id: The model ID used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_config: Dict with 'cost_per_1k_input_tokens' and 'cost_per_1k_output_tokens'

        Returns:
            Total cost in USD
        """
        input_cost = (input_tokens / 1000) * cost_config["cost_per_1k_input_tokens"]
        output_cost = (output_tokens / 1000) * cost_config["cost_per_1k_output_tokens"]
        total_cost = input_cost + output_cost

        logger.debug(
            f"Cost calculation for {model_id}: "
            f"${input_cost:.6f} (input) + ${output_cost:.6f} (output) = ${total_cost:.6f}"
        )

        return total_cost
