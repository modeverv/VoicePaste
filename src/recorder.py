"""Audio recording with chunk and full buffers."""

from __future__ import annotations

import queue
import threading
from types import TracebackType
from typing import Any

import numpy as np
from numpy.typing import NDArray

AudioArray = NDArray[np.float32]


class Recorder:
    """Record microphone audio into chunk and full buffers."""

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_seconds: int = 3,
        chunk_queue: queue.Queue[AudioArray] | None = None,
        channels: int = 1,
    ) -> None:
        """Create a recorder.

        Args:
            sample_rate: Audio sample rate in Hz.
            chunk_seconds: Seconds per preview chunk.
            chunk_queue: Queue that receives chunk arrays.
            channels: Input channel count.
        """

        self.sample_rate = sample_rate
        self.chunk_seconds = chunk_seconds
        self.chunk_queue = chunk_queue or queue.Queue()
        self.channels = channels
        self._chunk_frames = sample_rate * chunk_seconds
        self._full_buffer: list[AudioArray] = []
        self._chunk_buffer: list[AudioArray] = []
        self._chunk_frame_count = 0
        self._stream: Any | None = None
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        """Return whether recording is active."""

        return self._recording

    def start(self) -> None:
        """Start recording from the default input device."""

        if self._recording:
            return
        import sounddevice as sd

        with self._lock:
            self._full_buffer = []
            self._chunk_buffer = []
            self._chunk_frame_count = 0
            self._recording = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> AudioArray:
        """Stop recording and return the full audio buffer."""

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            self._recording = False
            full = self._concat(self._full_buffer)
            if self._chunk_buffer:
                self.chunk_queue.put(self._concat(self._chunk_buffer))
                self._chunk_buffer = []
                self._chunk_frame_count = 0
            return full

    def _callback(
        self,
        indata: AudioArray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del time_info, status
        mono = np.asarray(indata, dtype=np.float32).reshape(frames, -1).mean(axis=1)
        with self._lock:
            if not self._recording:
                return
            self._full_buffer.append(mono.copy())
            self._chunk_buffer.append(mono.copy())
            self._chunk_frame_count += frames
            if self._chunk_frame_count >= self._chunk_frames:
                self.chunk_queue.put(self._concat(self._chunk_buffer))
                self._chunk_buffer = []
                self._chunk_frame_count = 0

    def __enter__(self) -> Recorder:
        """Start recording when entering a context."""

        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop recording when leaving a context."""

        del exc_type, exc_value, traceback
        self.stop()

    @staticmethod
    def _concat(parts: list[AudioArray]) -> AudioArray:
        if not parts:
            return np.array([], dtype=np.float32)
        return np.concatenate(parts).astype(np.float32, copy=False)
