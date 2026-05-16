"""Debug helpers for inspecting captured audio."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from src.recorder import AudioArray


def audio_rms(audio: AudioArray) -> float:
    """Return root mean square amplitude for a float audio buffer."""

    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))


def is_silent(audio: AudioArray, threshold: float = 1e-5) -> bool:
    """Return whether an audio buffer is effectively silent."""

    return audio_rms(audio) < threshold


def save_wav(audio: AudioArray, path: str | Path, sample_rate: int) -> None:
    """Save a mono float32 audio buffer as a 16-bit PCM WAV file.

    Args:
        audio: Mono audio samples in the usual float range of -1.0 to 1.0.
        path: Output WAV path.
        sample_rate: Audio sample rate in Hz.
    """

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767).astype("<i2")
    with wave.open(str(output_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.tobytes())
