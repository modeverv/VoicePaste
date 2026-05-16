"""Rule-based formatter backend."""

from __future__ import annotations

import re

from src.config import FormatterConfig
from src.formatter import PostFormatter


class RuleFormatter(PostFormatter):
    """Dependency-free rule-based Japanese text formatter."""

    def __init__(self, config: FormatterConfig) -> None:
        """Initialize the formatter from formatter config."""

        self.config = config
        escaped = sorted(
            (re.escape(item) for item in config.fillers if item),
            key=len,
            reverse=True,
        )
        self._filler_pattern = re.compile("|".join(escaped)) if escaped else None

    def format(self, text: str) -> str:
        """Remove fillers and normalize punctuation."""

        formatted = text.strip()
        if self.config.remove_fillers and self._filler_pattern is not None:
            formatted = self._filler_pattern.sub("", formatted)
        formatted = re.sub(r"\s+", " ", formatted).strip()
        formatted = re.sub(r"([。、,.!?！？])\1+", r"\1", formatted)
        formatted = re.sub(r"\s+([。、,.!?！？])", r"\1", formatted)
        if self.config.add_punctuation:
            formatted = self._add_punctuation(formatted)
        return formatted

    def _add_punctuation(self, text: str) -> str:
        if not text:
            return text
        if "。" not in text and len(text) > 50 and "、" not in text:
            text = self._insert_comma(text)
        if not re.search(r"[。.!?！？]$", text):
            text += "。"
        return text

    def _insert_comma(self, text: str) -> str:
        candidates = ["ので", "けど", "から", "して", "ます", "です"]
        midpoint = len(text) // 2
        best_index = -1
        best_distance = len(text)
        for token in candidates:
            start = text.find(token)
            while start != -1:
                index = start + len(token)
                distance = abs(index - midpoint)
                if 10 < index < len(text) - 10 and distance < best_distance:
                    best_index = index
                    best_distance = distance
                start = text.find(token, start + 1)
        if best_index == -1:
            best_index = midpoint
        return f"{text[:best_index]}、{text[best_index:]}"
