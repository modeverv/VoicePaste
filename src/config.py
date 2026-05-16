"""Configuration loading for VoicePaste."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_FILLERS = ["あー", "えっと", "なんか", "えー", "あの", "まあ", "ちょっと待って"]


@dataclass(frozen=True)
class LLMFormatterConfig:
    """Configuration for the future local LLM formatter backend."""

    endpoint: str = "http://localhost:1234/v1"
    model: str = "auto"
    prompt: str = ""


@dataclass(frozen=True)
class FormatterConfig:
    """Text formatter configuration."""

    backend: str = "rule"
    remove_fillers: bool = True
    add_punctuation: bool = True
    fillers: list[str] = field(default_factory=lambda: list(DEFAULT_FILLERS))
    llm: LLMFormatterConfig = field(default_factory=LLMFormatterConfig)


@dataclass(frozen=True)
class Config:
    """VoicePaste application configuration."""

    hotkey: str = "<cmd>+<shift>+space"
    model: str = "base"
    language: str = "ja"
    device: str = "auto"
    chunk_seconds: int = 3
    formatter: FormatterConfig = field(default_factory=FormatterConfig)


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_config(path: str | Path = "config.yaml") -> Config:
    """Load a YAML config file and merge it with built-in defaults.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        A typed configuration object.
    """

    config_path = Path(path)
    raw: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw = _as_mapping(loaded)

    defaults = Config()
    formatter_raw = _as_mapping(raw.get("formatter"))
    llm_raw = _as_mapping(formatter_raw.get("llm"))

    llm = LLMFormatterConfig(
        endpoint=str(llm_raw.get("endpoint", defaults.formatter.llm.endpoint)),
        model=str(llm_raw.get("model", defaults.formatter.llm.model)),
        prompt=str(llm_raw.get("prompt", defaults.formatter.llm.prompt)),
    )
    formatter = FormatterConfig(
        backend=str(formatter_raw.get("backend", defaults.formatter.backend)),
        remove_fillers=bool(formatter_raw.get("remove_fillers", defaults.formatter.remove_fillers)),
        add_punctuation=bool(
            formatter_raw.get("add_punctuation", defaults.formatter.add_punctuation)
        ),
        fillers=list(formatter_raw.get("fillers", defaults.formatter.fillers)),
        llm=llm,
    )
    return Config(
        hotkey=str(raw.get("hotkey", defaults.hotkey)),
        model=str(raw.get("model", defaults.model)),
        language=str(raw.get("language", defaults.language)),
        device=str(raw.get("device", defaults.device)),
        chunk_seconds=int(raw.get("chunk_seconds", defaults.chunk_seconds)),
        formatter=formatter,
    )
