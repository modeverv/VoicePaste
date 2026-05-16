"""faster-whisper backend."""

from __future__ import annotations

from typing import Any

from numpy.typing import NDArray


class FasterWhisperBackend:
    """Whisper backend using faster-whisper."""

    def __init__(self, model: str, device: str, language: str) -> None:
        """Store model configuration."""

        self.model_name = model
        self.device = "cpu" if device == "auto" else device
        self.language = language
        self._model: Any | None = None

    def load(self) -> None:
        """Load the faster-whisper model."""

        from faster_whisper import WhisperModel

        compute_type = "int8" if self.device == "cpu" else "float16"
        self._model = WhisperModel(self.model_name, device=self.device, compute_type=compute_type)

    def transcribe(self, audio: NDArray[Any]) -> str:
        """Transcribe a full audio buffer."""

        model = self._require_model()
        segments, _info = model.transcribe(audio, language=self.language, vad_filter=True)
        return "".join(segment.text for segment in segments).strip()

    def transcribe_chunk(self, audio: NDArray[Any]) -> str:
        """Transcribe a short preview chunk."""

        model = self._require_model()
        segments, _info = model.transcribe(
            audio,
            language=self.language,
            beam_size=1,
            vad_filter=False,
        )
        return "".join(segment.text for segment in segments).strip()

    def _require_model(self) -> Any:
        if self._model is None:
            raise RuntimeError("Transcriber backend is not loaded.")
        return self._model
