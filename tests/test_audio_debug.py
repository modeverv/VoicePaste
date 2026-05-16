from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from src.audio_debug import audio_rms, is_silent, save_wav


def test_audio_rms_and_silence_detection() -> None:
    assert audio_rms(np.array([0.0, 0.0], dtype=np.float32)) == 0.0
    assert is_silent(np.array([0.0, 0.0], dtype=np.float32)) is True
    assert is_silent(np.array([0.1, 0.0], dtype=np.float32)) is False


def test_save_wav_writes_mono_pcm16(tmp_path: Path) -> None:
    path = tmp_path / "debug" / "sample.wav"

    save_wav(np.array([-1.0, 0.0, 1.0], dtype=np.float32), path, 16000)

    with wave.open(str(path), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getframerate() == 16000
        assert wav.getnframes() == 3
        frames = wav.readframes(3)

    assert np.frombuffer(frames, dtype="<i2").tolist() == [-32767, 0, 32767]
