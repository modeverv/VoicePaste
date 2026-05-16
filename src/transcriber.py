"""Whisper backend selection and transcription facade."""

from __future__ import annotations

import platform
from typing import Protocol

from numpy.typing import NDArray

from src.config import Config


class TranscriberBackend(Protocol):
    """Protocol shared by Whisper backends."""

    def load(self) -> None:
        """Load model resources."""

    def transcribe(self, audio: NDArray) -> str:
        """Transcribe a full audio buffer."""

    def transcribe_chunk(self, audio: NDArray) -> str:
        """Transcribe a preview chunk."""


class Transcriber:
    """Select and expose the best Whisper backend for the current platform."""

    def __init__(self, config: Config, backend: TranscriberBackend | None = None) -> None:
        """Create a transcriber facade."""

        self.config = config
        self.backend = backend or self._create_backend(config)

    def load(self) -> None:
        """Load the configured backend model."""

        self.backend.load()

    def transcribe(self, audio: NDArray) -> str:
        """Transcribe a full recording."""

        return self.backend.transcribe(audio)

    def transcribe_chunk(self, audio: NDArray) -> str:
        """Transcribe a preview chunk."""

        return self.backend.transcribe_chunk(audio)

    @staticmethod
    def _create_backend(config: Config) -> TranscriberBackend:
        system = platform.system()
        machine = platform.machine().lower()
        if (
            system == "Darwin"
            and machine in {"arm64", "aarch64"}
            and config.device in {"auto", "mlx"}
        ):
            from src.backends.mlx import MLXWhisperBackend

            return MLXWhisperBackend(config.model, config.device, config.language)
        from src.backends.faster import FasterWhisperBackend

        return FasterWhisperBackend(config.model, config.device, config.language)
