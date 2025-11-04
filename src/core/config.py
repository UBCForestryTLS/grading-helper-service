"""Configuration management for loading YAML configs and environment variables."""

from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class ConfigLoader:
    """Loads and manages configuration from YAML files."""

    def __init__(self, config_dir: Path | None = None):
        """
        Initialize the config loader.

        Args:
            config_dir: Path to config directory (defaults to project root/config)
        """
        if config_dir is None:
            # Assume we're in src/core, go up two levels to root, then into config
            self.config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

        self.config: dict[str, Any] = {}
        self.prompts: dict[str, Any] = {}

    def load_config(self) -> dict[str, Any]:
        """
        Load the main configuration from config.yaml.

        Returns:
            Configuration dictionary
        """
        config_path = self.config_dir / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        return self.config

    def load_prompts(self) -> dict[str, Any]:
        """
        Load prompt templates from prompts.yaml.

        Returns:
            Prompts dictionary
        """
        prompts_path = self.config_dir / "prompts.yaml"

        if not prompts_path.exists():
            raise FileNotFoundError(f"Prompts file not found: {prompts_path}")

        with open(prompts_path) as f:
            self.prompts = yaml.safe_load(f)

        return self.prompts

    def get_model_config(self, model_id: str) -> dict[str, Any]:
        """
        Get configuration for a specific model.

        Args:
            model_id: The model ID to look up

        Returns:
            Model configuration dict

        Raises:
            ValueError: If model not found in config
        """
        if not self.config:
            self.load_config()

        models = self.config.get("models", [])

        for model in models:
            if model["id"] == model_id:
                return model

        raise ValueError(f"Model '{model_id}' not found in configuration")

    def get_system_prompt(self, version: str = "v1_basic") -> str:
        """
        Get a system prompt by version.

        Args:
            version: Prompt version (e.g., "v1_basic", "v2_strict", "v3_constructive")

        Returns:
            System prompt text

        Raises:
            ValueError: If prompt version not found
        """
        if not self.prompts:
            self.load_prompts()

        system_prompts = self.prompts.get("system_prompts", {})

        if version not in system_prompts:
            raise ValueError(
                f"Prompt version '{version}' not found. "
                f"Available: {list(system_prompts.keys())}"
            )

        return system_prompts[version]

    def get_grading_template(self, template_name: str = "standard") -> str:
        """
        Get a grading prompt template.

        Args:
            template_name: Template name (e.g., "standard", "with_context")

        Returns:
            Template string

        Raises:
            ValueError: If template not found
        """
        if not self.prompts:
            self.load_prompts()

        templates = self.prompts.get("grading_templates", {})

        if template_name not in templates:
            raise ValueError(
                f"Template '{template_name}' not found. " f"Available: {list(templates.keys())}"
            )

        return templates[template_name]


# Convenience functions for quick access
def load_config() -> dict[str, Any]:
    """Load the main configuration."""
    loader = ConfigLoader()
    return loader.load_config()


def load_prompts() -> dict[str, Any]:
    """Load prompt templates."""
    loader = ConfigLoader()
    return loader.load_prompts()


def get_model_config(model_id: str) -> dict[str, Any]:
    """Get config for a specific model."""
    loader = ConfigLoader()
    return loader.get_model_config(model_id)
