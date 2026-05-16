"""mlx-whisper backend for Apple Silicon."""

from __future__ import annotations

import queue
import threading
from typing import Any

from numpy.typing import NDArray

MLX_MODEL_ALIASES = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "tiny.en": "mlx-community/whisper-tiny.en-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "base.en": "mlx-community/whisper-base.en-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "small.en": "mlx-community/whisper-small.en-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "medium.en": "mlx-community/whisper-medium.en-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
    "large-v2": "mlx-community/whisper-large-v2-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


def resolve_mlx_model_name(model: str) -> str:
    """Resolve OpenAI Whisper size aliases to MLX-compatible model IDs.

    Args:
        model: A short model size, Hugging Face repo ID, or local model path.

    Returns:
        The MLX-compatible repo ID or original custom value.
    """

    return MLX_MODEL_ALIASES.get(model, model)


class MLXWhisperBackend:
    """Whisper backend using mlx-whisper."""

    def __init__(self, model: str, device: str, language: str) -> None:
        """Store model configuration."""

        del device
        self.model_name = resolve_mlx_model_name(model)
        self.language = language
        self._requests: queue.Queue[tuple[str, NDArray[Any] | None, queue.Queue[Any]]] = (
            queue.Queue()
        )
        self._worker: threading.Thread | None = None
        self._loaded = False

    def load(self) -> None:
        """Download/cache and load the model on the dedicated MLX worker thread."""

        if self._loaded:
            return
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        self._submit("load", None)
        self._loaded = True

    def _worker_loop(self) -> None:
        import mlx.core as mx
        from mlx_whisper import transcribe
        from mlx_whisper.transcribe import ModelHolder

        while True:
            command, audio, response = self._requests.get()
            try:
                if command == "load":
                    ModelHolder.get_model(self.model_name, mx.float16)
                    response.put(None)
                elif command == "transcribe":
                    if audio is None:
                        raise RuntimeError("Audio is required for transcription.")
                    result = transcribe(
                        audio,
                        path_or_hf_repo=self.model_name,
                        language=self.language,
                    )
                    response.put(result)
                else:
                    raise RuntimeError(f"Unknown MLX worker command: {command}")
            except Exception as exc:
                response.put(exc)

    def transcribe(self, audio: NDArray[Any]) -> str:
        """Transcribe a full audio buffer."""

        result = self._call("transcribe", audio)
        return str(result.get("text", "")).strip()

    def transcribe_chunk(self, audio: NDArray[Any]) -> str:
        """Transcribe a short preview chunk."""

        result = self._call("transcribe", audio)
        return str(result.get("text", "")).strip()

    def _call(self, command: str, audio: NDArray[Any]) -> dict[str, Any]:
        result = self._submit(command, audio)
        if not isinstance(result, dict):
            raise RuntimeError("MLX transcription did not return a result dictionary.")
        return result

    def _submit(self, command: str, audio: NDArray[Any] | None) -> Any:
        if self._worker is None:
            raise RuntimeError("Transcriber backend is not loaded.")
        response: queue.Queue[Any] = queue.Queue(maxsize=1)
        self._requests.put((command, audio, response))
        result = response.get()
        if isinstance(result, Exception):
            raise result
        return result
