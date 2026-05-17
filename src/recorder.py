"""Audio recording with chunk and full buffers."""

from __future__ import annotations

import queue
import threading
from types import TracebackType
from typing import Any

import numpy as np
from numpy.typing import NDArray

from src.mic_level import MicLevel, measure_level

AudioArray = NDArray[np.float32]
InputDevice = int | str | None


class Recorder:
    """Record microphone audio into chunk and full buffers."""

    def __init__(
        self,
        sample_rate: int = 16000,
        input_sample_rate: int | str = "auto",
        chunk_seconds: int = 3,
        chunk_queue: queue.Queue[AudioArray] | None = None,
        channels: int = 1,
        device: InputDevice = None,
    ) -> None:
        """Create a recorder.

        Args:
            sample_rate: Output audio sample rate in Hz for Whisper.
            input_sample_rate: Input device sample rate, or "auto" for device default.
            chunk_seconds: Seconds per preview chunk.
            chunk_queue: Queue that receives chunk arrays.
            channels: Input channel count.
            device: Optional sounddevice input device index or name.
        """

        self.sample_rate = sample_rate
        self.input_sample_rate = input_sample_rate
        self.chunk_seconds = chunk_seconds
        self.chunk_queue = chunk_queue or queue.Queue()
        self.channels = channels
        self.device = device
        self._capture_sample_rate = sample_rate
        self._chunk_frames = sample_rate * chunk_seconds
        self._full_buffer: list[AudioArray] = []
        self._chunk_buffer: list[AudioArray] = []
        self._chunk_frame_count = 0
        self._stream: Any | None = None
        self._latest_level = MicLevel()
        self._lock = threading.Lock()
        self._recording = False

    @property
    def is_recording(self) -> bool:
        """Return whether recording is active."""

        return self._recording

    @property
    def latest_level(self) -> MicLevel:
        """Return the latest level measured from the active recording stream."""

        with self._lock:
            return self._latest_level

    def start(self) -> None:
        """Start recording from the default input device."""

        if self._recording:
            return
        import sounddevice as sd

        self._capture_sample_rate = self._resolve_capture_sample_rate(sd)
        self._chunk_frames = self._capture_sample_rate * self.chunk_seconds
        with self._lock:
            self._full_buffer = []
            self._chunk_buffer = []
            self._chunk_frame_count = 0
            self._latest_level = MicLevel()
            self._recording = True
        self._stream = sd.InputStream(
            samplerate=self._capture_sample_rate,
            device=self.device,
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
            full = self._to_output_rate(self._concat(self._full_buffer))
            if self._chunk_buffer:
                self.chunk_queue.put(self._to_output_rate(self._concat(self._chunk_buffer)))
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
        level = measure_level(indata)
        with self._lock:
            if not self._recording:
                return
            self._latest_level = level
            self._full_buffer.append(mono.copy())
            self._chunk_buffer.append(mono.copy())
            self._chunk_frame_count += frames
            if self._chunk_frame_count >= self._chunk_frames:
                self.chunk_queue.put(self._to_output_rate(self._concat(self._chunk_buffer)))
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

    def _resolve_capture_sample_rate(self, sounddevice: Any) -> int:
        if self.input_sample_rate != "auto":
            return int(self.input_sample_rate)
        device_info = sounddevice.query_devices(self.device, "input")
        return int(device_info["default_samplerate"])

    def _to_output_rate(self, audio: AudioArray) -> AudioArray:
        if audio.size == 0 or self._capture_sample_rate == self.sample_rate:
            return audio.astype(np.float32, copy=False)
        duration = audio.size / self._capture_sample_rate
        output_size = max(1, int(round(duration * self.sample_rate)))
        source_positions = np.linspace(0, audio.size - 1, num=audio.size)
        target_positions = np.linspace(0, audio.size - 1, num=output_size)
        return np.interp(target_positions, source_positions, audio).astype(np.float32)
