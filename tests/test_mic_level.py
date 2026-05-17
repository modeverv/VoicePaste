from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from src.mic_level import MicLevel, MicLevelMonitor, format_mic_level, measure_level


class FakeInputStream:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.start = Mock()
        self.stop = Mock()
        self.close = Mock()


def test_measure_level_calculates_rms_and_peak() -> None:
    level = measure_level(np.array([[0.0], [0.5], [-0.5], [1.0]], dtype=np.float32))

    assert level.rms == pytest.approx(0.6123724)
    assert level.peak == pytest.approx(1.0)
    assert level.rms_dbfs == pytest.approx(-4.259, abs=0.001)


def test_format_mic_level_uses_dbfs() -> None:
    text = format_mic_level(MicLevel(rms=0.01, peak=0.1))

    assert text == "RMS  -40.0 dBFS  Peak  -20.0 dBFS"


def test_monitor_starts_sounddevice_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_stream = FakeInputStream()
    factory = Mock(return_value=fake_stream)
    query_devices = Mock(return_value={"default_samplerate": 44100.0})
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(InputStream=factory, query_devices=query_devices),
    )
    monitor = MicLevelMonitor(device=2, input_sample_rate="auto", update_ms=100)

    monitor.start()
    monitor.stop()

    query_devices.assert_called_once_with(2, "input")
    factory.assert_called_once()
    assert factory.call_args.kwargs["samplerate"] == 44100
    assert factory.call_args.kwargs["device"] == 2
    assert factory.call_args.kwargs["channels"] == 1
    assert factory.call_args.kwargs["dtype"] == "float32"
    fake_stream.start.assert_called_once()
    fake_stream.stop.assert_called_once()
    fake_stream.close.assert_called_once()


def test_monitor_callback_updates_latest_level() -> None:
    monitor = MicLevelMonitor(update_ms=0)

    monitor._callback(np.array([[0.25], [-0.25]], dtype=np.float32), 2, None, None)

    assert monitor.latest_level.rms == pytest.approx(0.25)
    assert monitor.latest_level.peak == pytest.approx(0.25)
