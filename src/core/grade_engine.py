"""Core grading engine that orchestrates the grading process."""

import json
import logging
from typing import Any

from .bedrock_client import BedrockClient
from .config import ConfigLoader

logger = logging.getLogger(__name__)


class GradingEngine:
    """
    Orchestrates the grading process using AWS Bedrock and Claude models.

    Handles prompt formatting, model invocation, response parsing, and cost tracking.
    """

    def __init__(
        self, bedrock_client: BedrockClient | None = None, config_loader: ConfigLoader | None = None
    ):
        """
        Initialize the grading engine.

        Args:
            bedrock_client: BedrockClient instance (creates new one if None)
            config_loader: ConfigLoader instance (creates new one if None)
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        self.config_loader = config_loader or ConfigLoader()

        # Load configurations
        self.config = self.config_loader.load_config()
        self.prompts = self.config_loader.load_prompts()

        logger.info("Initialized GradingEngine")

    def grade_submission(
        self,
        question: str,
        rubric: dict[str, Any],
        student_response: str,
        system_prompt_version: str = "v1_basic",
        model_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        additional_context: str | None = None,
        course_context: str | None = None,
    ) -> dict[str, Any]:
        """
        Grade a student submission.

        Args:
            question: The assignment question text
            rubric: Rubric dictionary with grading criteria
            student_response: The student's answer
            system_prompt_version: Which system prompt to use (v1_basic, v2_strict, v3_constructive)
            model_id: Override default model (from config if None)
            temperature: Override default temperature (from config if None)
            max_tokens: Override default max_tokens (from config if None)
            additional_context: Any additional context for grading
            course_context: Course-specific context

        Returns:
            Dictionary with grading results including:
                - grade: Numerical grade
                - total_points: Total possible points
                - feedback: Detailed feedback text
                - strengths: List of strengths
                - improvements: List of areas for improvement
                - metadata: Model info, tokens, cost, timestamp
        """
        # Get default values from config
        if model_id is None:
            model_id = self.config["grading"]["default_model"]

        if temperature is None:
            temperature = self.config["grading"]["temperature"]

        if max_tokens is None:
            max_tokens = self.config["grading"]["max_tokens"]

        # Get system prompt
        system_prompt = self.config_loader.get_system_prompt(system_prompt_version)

        # Format the grading prompt
        user_prompt = self._format_grading_prompt(
            question=question,
            rubric=rubric,
            student_response=student_response,
            additional_context=additional_context,
            course_context=course_context,
        )

        # Prepare messages in Claude format
        messages = [{"role": "user", "content": user_prompt}]

        logger.info(
            f"Grading submission with model={model_id}, "
            f"system_prompt={system_prompt_version}, temp={temperature}"
        )

        # Invoke the model
        response = self.bedrock_client.invoke_model(
            model_id=model_id,
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Parse the response
        grading_result = self._parse_grading_response(response["response_text"])

        # Get model config for cost calculation
        model_config = self.config_loader.get_model_config(model_id)

        # Calculate cost
        cost = self.bedrock_client.calculate_cost(
            model_id=model_id,
            input_tokens=response["input_tokens"],
            output_tokens=response["output_tokens"],
            cost_config=model_config,
        )

        # Add metadata
        grading_result["metadata"] = {
            "model_id": model_id,
            "model_name": model_config["name"],
            "system_prompt_version": system_prompt_version,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "input_tokens": response["input_tokens"],
            "output_tokens": response["output_tokens"],
            "total_tokens": response["input_tokens"] + response["output_tokens"],
            "cost_usd": cost,
            "timestamp": response["timestamp"],
        }

        logger.info(
            f"Grading complete. Grade: {grading_result.get('grade')}/{grading_result.get('total_points')}, "
            f"Cost: ${cost:.4f}"
        )

        return grading_result

    def _format_grading_prompt(
        self,
        question: str,
        rubric: dict[str, Any],
        student_response: str,
        additional_context: str | None = None,
        course_context: str | None = None,
    ) -> str:
        """
        Format the grading prompt with question, rubric, and student response.

        Args:
            question: Assignment question
            rubric: Grading rubric
            student_response: Student's answer
            additional_context: Optional additional context
            course_context: Optional course context

        Returns:
            Formatted prompt string
        """
        # Format the rubric as readable text
        rubric_text = self._format_rubric(rubric)

        # Choose template based on whether we have additional context
        if course_context or additional_context:
            template = self.config_loader.get_grading_template("with_context")
            prompt = template.format(
                course_context=course_context or "N/A",
                question=question,
                rubric=rubric_text,
                student_response=student_response,
                additional_context=additional_context or "N/A",
            )
        else:
            template = self.config_loader.get_grading_template("standard")
            prompt = template.format(
                question=question, rubric=rubric_text, student_response=student_response
            )

        # Add instruction for JSON output
        prompt += "\n\nPlease provide your evaluation in the following JSON format:\n"
        prompt += json.dumps(
            {
                "grade": "<numerical grade>",
                "total_points": "<total possible points>",
                "feedback": "<detailed explanation of the grade>",
                "strengths": ["<strength 1>", "<strength 2>"],
                "improvements": ["<area for improvement 1>", "<area for improvement 2>"],
            },
            indent=2,
        )

        return prompt

    def _format_rubric(self, rubric: dict[str, Any]) -> str:
        """
        Format rubric dictionary as readable text.

        Args:
            rubric: Rubric dictionary

        Returns:
            Formatted rubric string
        """
        lines = [f"Total Points: {rubric.get('total_points', 'N/A')}\n"]

        criteria = rubric.get("criteria", [])
        if criteria:
            lines.append("Grading Criteria:")
            for i, criterion in enumerate(criteria, 1):
                lines.append(
                    f"\n{i}. {criterion.get('criterion', 'N/A')} "
                    f"({criterion.get('points', 0)} points)"
                )
                lines.append(f"   {criterion.get('description', '')}")

        return "\n".join(lines)

    def _parse_grading_response(self, response_text: str) -> dict[str, Any]:
        """
        Parse the LLM's grading response.

        Attempts to extract JSON from the response. If that fails, returns
        a structured error with the raw text.

        Args:
            response_text: Raw response from the LLM

        Returns:
            Parsed grading result dictionary
        """
        try:
            # Try to find JSON in the response
            # Look for content between { and }
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                return result
            else:
                logger.warning("No JSON found in response, returning raw text")
                return {
                    "grade": None,
                    "total_points": None,
                    "feedback": response_text,
                    "strengths": [],
                    "improvements": [],
                    "parse_error": "No JSON found in response",
                }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return {
                "grade": None,
                "total_points": None,
                "feedback": response_text,
                "strengths": [],
                "improvements": [],
                "parse_error": f"JSON decode error: {str(e)}",
            }
