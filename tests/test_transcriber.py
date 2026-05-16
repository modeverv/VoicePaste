from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from src.config import Config
from src.transcriber import Transcriber


class FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeBackend:
    def __init__(self) -> None:
        self.load = Mock()
        self.transcribe = Mock(return_value="full")
        self.transcribe_chunk = Mock(return_value="chunk")


def test_transcriber_delegates_to_backend() -> None:
    backend = FakeBackend()
    transcriber = Transcriber(Config(), backend=backend)
    audio = np.zeros(10, dtype=np.float32)

    transcriber.load()

    assert transcriber.transcribe(audio) == "full"
    assert transcriber.transcribe_chunk(audio) == "chunk"
    backend.load.assert_called_once()


def test_create_backend_uses_mlx_on_apple_silicon(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    monkeypatch.setattr("platform.machine", lambda: "arm64")

    backend = Transcriber(Config()).backend

    assert backend.__class__.__name__ == "MLXWhisperBackend"


def test_create_backend_uses_faster_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    backend = Transcriber(Config()).backend

    assert backend.__class__.__name__ == "FasterWhisperBackend"


def test_faster_backend_transcribes_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backends.faster import FasterWhisperBackend

    model = Mock()
    model.transcribe.return_value = ([FakeSegment(" hello"), FakeSegment(" world ")], object())
    whisper_model = Mock(return_value=model)
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=whisper_model),
    )
    backend = FasterWhisperBackend("base", "auto", "ja")

    backend.load()

    assert backend.transcribe(np.zeros(10, dtype=np.float32)) == "hello world"
    whisper_model.assert_called_once_with("base", device="cpu", compute_type="int8")


def test_mlx_backend_transcribes_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backends.mlx import MLXWhisperBackend

    transcribe = Mock(return_value={"text": " テスト "})
    monkeypatch.setitem(sys.modules, "mlx_whisper", SimpleNamespace(transcribe=transcribe))
    backend = MLXWhisperBackend("base", "auto", "ja")

    backend.load()

    assert backend.transcribe_chunk(np.zeros(10, dtype=np.float32)) == "テスト"
