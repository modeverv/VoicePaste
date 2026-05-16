from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src import mic_check


class FakeInputStream:
    def __init__(self, callback: object, **kwargs: object) -> None:
        self.callback = callback
        self.kwargs = kwargs

    def __enter__(self) -> FakeInputStream:
        audio = np.array([[0.1], [0.0], [-0.1]], dtype=np.float32)
        self.callback(audio, 3, None, None)
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        del exc_type, exc_value, traceback


def test_device_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVICE", "1")
    assert mic_check._device_from_env(None) == 1

    monkeypatch.setenv("DEVICE", "MacBook Proのマイク")
    assert mic_check._device_from_env(None) == "MacBook Proのマイク"

    monkeypatch.delenv("DEVICE")
    assert mic_check._device_from_env("default") == "default"


def test_mic_check_main_records_and_saves_debug_wav(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    devices = [
        {
            "name": "MacBook Proのマイク",
            "max_input_channels": 1,
            "default_samplerate": 48000.0,
        }
    ]

    def query_devices(device: object = None, kind: str | None = None) -> object:
        if kind == "input":
            return devices[0]
        return devices

    fake_sd = SimpleNamespace(
        query_devices=query_devices,
        InputStream=lambda **kwargs: FakeInputStream(**kwargs),
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SECONDS", "1")
    monkeypatch.delenv("DEVICE", raising=False)

    mic_check.main()

    output = capsys.readouterr().out
    assert "microphone input detected" in output
    assert (tmp_path / "debug" / "mic_check.wav").exists()
