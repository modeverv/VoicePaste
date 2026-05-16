"""Post-transcription formatter interface and factory."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.config import FormatterConfig


class PostFormatter(ABC):
    """Interface for final transcription text formatting."""

    @abstractmethod
    def format(self, text: str) -> str:
        """Format raw Whisper text."""

    @classmethod
    def from_config(cls, config: FormatterConfig) -> PostFormatter:
        """Create a formatter backend from config."""

        if config.backend == "rule":
            from src.formatter.backends.rule import RuleFormatter

            return RuleFormatter(config)
        if config.backend == "llm":
            from src.formatter.backends.llm import LLMFormatter

            return LLMFormatter(config)
        raise ValueError(f"Unknown formatter backend: {config.backend}")


__all__ = ["PostFormatter"]
