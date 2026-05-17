from __future__ import annotations

import builtins
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
    model_holder = SimpleNamespace(get_model=Mock())
    mlx_core = SimpleNamespace(float16="float16")
    monkeypatch.setitem(sys.modules, "mlx_whisper", SimpleNamespace(transcribe=transcribe))
    monkeypatch.setitem(
        sys.modules,
        "mlx_whisper.transcribe",
        SimpleNamespace(ModelHolder=model_holder),
    )
    monkeypatch.setitem(sys.modules, "mlx", SimpleNamespace(core=mlx_core))
    monkeypatch.setitem(sys.modules, "mlx.core", mlx_core)
    backend = MLXWhisperBackend("base", "auto", "ja")

    backend.load()

    model_holder.get_model.assert_called_once_with("mlx-community/whisper-base-mlx", "float16")
    assert backend.transcribe_chunk(np.zeros(10, dtype=np.float32)) == "テスト"
    transcribe.assert_called_once()
    assert transcribe.call_args.kwargs["path_or_hf_repo"] == "mlx-community/whisper-base-mlx"


def test_mlx_backend_preserves_custom_model_path() -> None:
    from src.backends.mlx import resolve_mlx_model_name

    assert resolve_mlx_model_name("/models/whisper-base-mlx") == "/models/whisper-base-mlx"
    assert resolve_mlx_model_name("org/custom-model") == "org/custom-model"


def test_mlx_backend_load_reports_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.backends.mlx import MLXWhisperBackend

    real_import = builtins.__import__

    def block_mlx_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "mlx" or name.startswith("mlx."):
            raise ModuleNotFoundError("No module named 'mlx'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", block_mlx_import)
    backend = MLXWhisperBackend("base", "auto", "ja")

    with pytest.raises(ModuleNotFoundError):
        backend.load()
