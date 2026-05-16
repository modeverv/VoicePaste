"""Stub local LLM formatter backend."""

from __future__ import annotations

from src.config import FormatterConfig
from src.formatter import PostFormatter


class LLMFormatter(PostFormatter):
    """Future local LLM formatter backend."""

    def __init__(self, config: FormatterConfig) -> None:
        """Store LLM formatter config for future implementation."""

        self.config = config

    def format(self, text: str) -> str:
        """Raise until the local LLM formatter is implemented."""

        raise NotImplementedError("LLMFormatter is not yet implemented.")
