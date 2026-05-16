"""mlx-whisper backend for Apple Silicon."""

from __future__ import annotations

from typing import Any

from numpy.typing import NDArray


class MLXWhisperBackend:
    """Whisper backend using mlx-whisper."""

    def __init__(self, model: str, device: str, language: str) -> None:
        """Store model configuration."""

        del device
        self.model_name = model
        self.language = language
        self._transcribe: Any | None = None

    def load(self) -> None:
        """Load the mlx-whisper transcribe function."""

        from mlx_whisper import transcribe

        self._transcribe = transcribe

    def transcribe(self, audio: NDArray[Any]) -> str:
        """Transcribe a full audio buffer."""

        result = self._call(audio)
        return str(result.get("text", "")).strip()

    def transcribe_chunk(self, audio: NDArray[Any]) -> str:
        """Transcribe a short preview chunk."""

        result = self._call(audio)
        return str(result.get("text", "")).strip()

    def _call(self, audio: NDArray[Any]) -> dict[str, Any]:
        if self._transcribe is None:
            raise RuntimeError("Transcriber backend is not loaded.")
        return self._transcribe(audio, path_or_hf_repo=self.model_name, language=self.language)
