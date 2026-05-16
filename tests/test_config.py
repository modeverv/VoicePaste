from __future__ import annotations

from pathlib import Path

from src.config import DEFAULT_FILLERS, load_config


def test_load_config_defaults_when_file_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.yaml")

    assert config.hotkey == "<cmd>+<shift>+space"
    assert config.model == "base"
    assert config.language == "ja"
    assert config.input_device is None
    assert config.input_sample_rate == "auto"
    assert config.sample_rate == 16000
    assert config.chunk_seconds == 3
    assert config.debug_audio_path == "debug/last_recording.wav"
    assert config.formatter.backend == "rule"
    assert config.formatter.fillers == DEFAULT_FILLERS


def test_load_config_merges_partial_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        """
model: small
input_device: "MacBook Proのマイク"
input_sample_rate: 48000
sample_rate: 8000
chunk_seconds: 5
debug_audio_path: tmp/input.wav
formatter:
  backend: llm
  remove_fillers: false
  llm:
    model: japanese-editor
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.model == "small"
    assert config.input_device == "MacBook Proのマイク"
    assert config.input_sample_rate == 48000
    assert config.sample_rate == 8000
    assert config.chunk_seconds == 5
    assert config.debug_audio_path == "tmp/input.wav"
    assert config.hotkey == "<cmd>+<shift>+space"
    assert config.formatter.backend == "llm"
    assert config.formatter.remove_fillers is False
    assert config.formatter.add_punctuation is True
    assert config.formatter.llm.model == "japanese-editor"
    assert config.formatter.llm.endpoint == "http://localhost:1234/v1"
