#!/usr/bin/env python3
"""
Quick test script to verify the grading pipeline works end-to-end.

Usage:
    python test_grading.py
"""

import json
import logging
from pathlib import Path

from src.core.grade_engine import GradingEngine

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Test the grading pipeline with the example submission."""

    logger.info("=" * 70)
    logger.info("Testing Grading Pipeline")
    logger.info("=" * 70)

    # Load the example submission
    example_path = Path("data/samples/example_submission.json")

    if not example_path.exists():
        logger.error(f"Example file not found: {example_path}")
        return

    with open(example_path) as f:
        submission_data = json.load(f)

    logger.info(f"\nLoaded example: {submission_data['assignment_id']}")
    logger.info(f"Question: {submission_data['question'][:100]}...")
    logger.info(f"Student response: {submission_data['student_response'][:100]}...")

    # Initialize the grading engine
    logger.info("\nInitializing grading engine...")
    engine = GradingEngine()

    # Grade the submission
    logger.info("\nGrading submission...")
    logger.info("This will call AWS Bedrock API - costs will be minimal (~$0.01)")

    try:
        result = engine.grade_submission(
            question=submission_data["question"],
            rubric=submission_data["rubric"],
            student_response=submission_data["student_response"],
            system_prompt_version="v1_basic",  # Try v2_strict or v3_constructive too!
        )

        # Display results
        logger.info("\n" + "=" * 70)
        logger.info("GRADING RESULTS")
        logger.info("=" * 70)

        print(f"\nGrade: {result['grade']}/{result['total_points']}")
        print(f"\nFeedback:\n{result['feedback']}")

        if result.get("strengths"):
            print("\nStrengths:")
            for strength in result["strengths"]:
                print(f"  • {strength}")

        if result.get("improvements"):
            print("\nAreas for Improvement:")
            for improvement in result["improvements"]:
                print(f"  • {improvement}")

        # Display metadata
        metadata = result["metadata"]
        print("\n" + "-" * 70)
        print(f"Model: {metadata['model_name']}")
        print(f"System Prompt: {metadata['system_prompt_version']}")
        print(f"Temperature: {metadata['temperature']}")
        print(
            f"Tokens: {metadata['input_tokens']} in, {metadata['output_tokens']} out, {metadata['total_tokens']} total"
        )
        print(f"Cost: ${metadata['cost_usd']:.4f}")
        print(f"Timestamp: {metadata['timestamp']}")

        # Save results
        output_path = Path("data/results/test_grading_result.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"\nResults saved to: {output_path}")
        logger.info("\nTest completed successfully!")

    except Exception as e:
        logger.error(f"\nTest failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
