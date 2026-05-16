from __future__ import annotations

import queue
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from src.recorder import Recorder


class FakeInputStream:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.start = Mock()
        self.stop = Mock()
        self.close = Mock()


def test_recorder_start_creates_sounddevice_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_stream = FakeInputStream()
    factory = Mock(return_value=fake_stream)
    query_devices = Mock(return_value={"default_samplerate": 48000.0})
    monkeypatch.setitem(
        sys.modules,
        "sounddevice",
        SimpleNamespace(InputStream=factory, query_devices=query_devices),
    )
    recorder = Recorder(sample_rate=16000, chunk_seconds=3)

    recorder.start()

    factory.assert_called_once()
    query_devices.assert_called_once_with(None, "input")
    assert factory.call_args.kwargs["samplerate"] == 48000
    assert factory.call_args.kwargs["device"] is None
    assert factory.call_args.kwargs["channels"] == 1
    assert factory.call_args.kwargs["dtype"] == "float32"
    fake_stream.start.assert_called_once()
    assert recorder.is_recording is True


def test_recorder_callback_splits_chunks_and_full_buffer() -> None:
    chunks: queue.Queue[np.ndarray] = queue.Queue()
    recorder = Recorder(sample_rate=4, chunk_seconds=2, chunk_queue=chunks)
    recorder._recording = True

    recorder._callback(np.ones((4, 1), dtype=np.float32), 4, None, None)
    recorder._callback(np.full((4, 1), 2, dtype=np.float32), 4, None, None)

    assert chunks.qsize() == 1
    np.testing.assert_array_equal(
        chunks.get(),
        np.array([1, 1, 1, 1, 2, 2, 2, 2], dtype=np.float32),
    )


def test_recorder_stop_returns_full_audio_and_flushes_partial_chunk() -> None:
    chunks: queue.Queue[np.ndarray] = queue.Queue()
    fake_stream = FakeInputStream()
    recorder = Recorder(sample_rate=4, chunk_seconds=2, chunk_queue=chunks)
    recorder._stream = fake_stream
    recorder._recording = True
    recorder._callback(np.ones((3, 1), dtype=np.float32), 3, None, None)

    full = recorder.stop()

    fake_stream.stop.assert_called_once()
    fake_stream.close.assert_called_once()
    np.testing.assert_array_equal(full, np.ones(3, dtype=np.float32))
    np.testing.assert_array_equal(chunks.get(), np.ones(3, dtype=np.float32))
    assert recorder.is_recording is False


def test_recorder_resamples_capture_audio_to_output_rate() -> None:
    recorder = Recorder(sample_rate=2, input_sample_rate=4)
    recorder._capture_sample_rate = 4

    output = recorder._to_output_rate(np.array([0, 1, 0, -1], dtype=np.float32))

    assert output.dtype == np.float32
    assert output.shape == (2,)
