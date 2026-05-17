"""Microphone level measurement helpers."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

InputDevice = int | str | None


@dataclass(frozen=True)
class MicLevel:
    """Current microphone level in normalized float audio units."""

    rms: float = 0.0
    peak: float = 0.0

    @property
    def rms_dbfs(self) -> float:
        """Return RMS level in dBFS."""

        return amplitude_to_dbfs(self.rms)

    @property
    def peak_dbfs(self) -> float:
        """Return peak level in dBFS."""

        return amplitude_to_dbfs(self.peak)


def amplitude_to_dbfs(amplitude: float, floor: float = -120.0) -> float:
    """Convert a normalized amplitude to dBFS."""

    if amplitude <= 0.0:
        return floor
    return max(floor, 20.0 * math.log10(amplitude))


def measure_level(indata: np.ndarray) -> MicLevel:
    """Measure mono RMS and peak values for a sounddevice callback buffer."""

    audio = np.asarray(indata, dtype=np.float32)
    if audio.size == 0:
        return MicLevel()
    mono = audio.reshape(audio.shape[0], -1).mean(axis=1)
    rms = float(np.sqrt(np.mean(mono.astype(np.float64) ** 2)))
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    return MicLevel(rms=rms, peak=peak)


def format_mic_level(level: MicLevel) -> str:
    """Format a microphone level for compact UI display."""

    return f"RMS {level.rms_dbfs:6.1f} dBFS  Peak {level.peak_dbfs:6.1f} dBFS"


class MicLevelMonitor:
    """Continuously sample microphone levels for a GUI meter."""

    def __init__(
        self,
        device: InputDevice = None,
        input_sample_rate: int | str = "auto",
        update_ms: int = 200,
    ) -> None:
        """Create a microphone level monitor.

        Args:
            device: Optional sounddevice input device index or name.
            input_sample_rate: Input device sample rate, or "auto" for device default.
            update_ms: Minimum interval between displayed level updates.
        """

        self.device = device
        self.input_sample_rate = input_sample_rate
        self.update_ms = update_ms
        self._stream: Any | None = None
        self._level = MicLevel()
        self._lock = threading.Lock()
        self._next_update = 0.0

    @property
    def latest_level(self) -> MicLevel:
        """Return the latest measured microphone level."""

        with self._lock:
            return self._level

    @property
    def is_running(self) -> bool:
        """Return whether the monitor stream is open."""

        return self._stream is not None

    def start(self) -> None:
        """Start the microphone monitor stream."""

        if self._stream is not None or self.update_ms <= 0:
            return
        import sounddevice as sd

        input_rate = self._resolve_input_sample_rate(sd)
        self._stream = sd.InputStream(
            samplerate=input_rate,
            device=self.device,
            channels=1,
            dtype="float32",
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop the microphone monitor stream."""

        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        del frames, time_info, status
        now = time.monotonic()
        with self._lock:
            if now < self._next_update:
                return
            self._level = measure_level(indata)
            self._next_update = now + (self.update_ms / 1000.0)

    def _resolve_input_sample_rate(self, sounddevice: Any) -> int:
        if self.input_sample_rate != "auto":
            return int(self.input_sample_rate)
        device_info = sounddevice.query_devices(self.device, "input")
        return int(device_info["default_samplerate"])
