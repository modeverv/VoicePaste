"""Configuration loading for VoicePaste."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

import yaml

DEFAULT_FILLERS = ["あー", "えっと", "なんか", "えー", "あの", "まあ", "ちょっと待って"]
DEFAULT_LLM_PROMPT = """\
あなたは音声入力の確定テキストを整形する編集者です。
Whisperの文字起こし結果を、意味を変えずに読みやすい日本語へ整えてください。
フィラー、言い直し、余分な空白を削り、必要な句読点を補ってください。
固有名詞、数値、コード、URLは推測で変更しないでください。
"""
InputDevice: TypeAlias = int | str | None


@dataclass(frozen=True)
class LLMFormatterConfig:
    """Configuration for the local LLM formatter backend."""

    endpoint: str = "http://localhost:1234/v1"
    model: str = "auto"
    prompt: str = DEFAULT_LLM_PROMPT
    backend: str = "auto"
    mlx_model: str = "mlx-community/gemma-4-e2b-it-4bit"
    gguf_repo_id: str = "mradermacher/gemma-4-E2B-it-GGUF"
    gguf_filename: str = "*Q4_K_M.gguf"
    models_dir: str = "models"
    max_tokens: int = 256
    temperature: float = 0.0
    n_ctx: int = 4096
    n_gpu_layers: int = -1


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
    input_device: InputDevice = None
    input_sample_rate: int | str = "auto"
    sample_rate: int = 16000
    chunk_seconds: int = 3
    mic_meter_update_ms: int = 200
    debug_audio_path: str = "debug/last_recording.wav"
    formatter: FormatterConfig = field(default_factory=FormatterConfig)


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_input_device(value: Any) -> InputDevice:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text or text.lower() in {"auto", "default", "none", "null"}:
        return None
    if text.isdigit():
        return int(text)
    return text


def _parse_input_sample_rate(value: Any) -> int | str:
    if value is None:
        return "auto"
    if isinstance(value, int):
        return value
    text = str(value).strip().lower()
    if text in {"", "auto", "default"}:
        return "auto"
    return int(text)


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

    _models_dir_raw = Path(str(llm_raw.get("models_dir", defaults.formatter.llm.models_dir)))
    _models_dir = (
        _models_dir_raw
        if _models_dir_raw.is_absolute()
        else config_path.parent.resolve() / _models_dir_raw
    )

    llm = LLMFormatterConfig(
        endpoint=str(llm_raw.get("endpoint", defaults.formatter.llm.endpoint)),
        model=str(llm_raw.get("model", defaults.formatter.llm.model)),
        prompt=str(llm_raw.get("prompt", defaults.formatter.llm.prompt)),
        backend=str(llm_raw.get("backend", defaults.formatter.llm.backend)),
        mlx_model=str(llm_raw.get("mlx_model", defaults.formatter.llm.mlx_model)),
        gguf_repo_id=str(llm_raw.get("gguf_repo_id", defaults.formatter.llm.gguf_repo_id)),
        gguf_filename=str(llm_raw.get("gguf_filename", defaults.formatter.llm.gguf_filename)),
        models_dir=str(_models_dir),
        max_tokens=int(llm_raw.get("max_tokens", defaults.formatter.llm.max_tokens)),
        temperature=float(llm_raw.get("temperature", defaults.formatter.llm.temperature)),
        n_ctx=int(llm_raw.get("n_ctx", defaults.formatter.llm.n_ctx)),
        n_gpu_layers=int(llm_raw.get("n_gpu_layers", defaults.formatter.llm.n_gpu_layers)),
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
        input_device=_parse_input_device(raw.get("input_device", defaults.input_device)),
        input_sample_rate=_parse_input_sample_rate(
            raw.get("input_sample_rate", defaults.input_sample_rate)
        ),
        sample_rate=int(raw.get("sample_rate", defaults.sample_rate)),
        chunk_seconds=int(raw.get("chunk_seconds", defaults.chunk_seconds)),
        mic_meter_update_ms=int(raw.get("mic_meter_update_ms", defaults.mic_meter_update_ms)),
        debug_audio_path=str(raw.get("debug_audio_path", defaults.debug_audio_path)),
        formatter=formatter,
    )
