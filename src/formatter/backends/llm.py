"""Local LLM formatter backend."""

from __future__ import annotations

import json
import os
import platform
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from src.config import FormatterConfig
from src.formatter import PostFormatter

STRUCTURED_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "formatted_text": {
            "type": "string",
            "description": "Whisper文字起こし結果を整形した最終テキスト。",
        },
    },
    "required": ["formatted_text"],
    "additionalProperties": False,
}


StatusCallback = Callable[[str], None]


class _LLMRunner(Protocol):
    def load(self, on_status: StatusCallback | None = None) -> None:
        """Download and load the local LLM."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a structured JSON string from prompts."""


class LLMFormatter(PostFormatter):
    """Format final Whisper text with a local Gemma 4 E2B model."""

    def __init__(self, config: FormatterConfig) -> None:
        """Initialize the local LLM formatter from formatter config."""

        self.config = config
        self.llm_config = config.llm
        self._runner: _LLMRunner | None = None

    def load(self, on_status: StatusCallback | None = None) -> None:
        """Download and load the local LLM backend."""

        self._get_runner().load(on_status=on_status)

    def format(self, text: str) -> str:
        """Format raw Whisper text using a local LLM."""

        stripped = text.strip()
        if not stripped:
            return stripped
        prompt = self._build_user_prompt(stripped)
        output = self._get_runner().generate(self._system_prompt(), prompt)
        formatted = self._parse_structured_output(output)
        if not formatted:
            raise RuntimeError("LLM formatter returned an empty response.")
        return formatted

    def _get_runner(self) -> _LLMRunner:
        if self._runner is None:
            self._runner = self._create_runner()
        return self._runner

    def _create_runner(self) -> _LLMRunner:
        backend = self.llm_config.backend.lower()
        if backend == "auto":
            backend = "mlx" if platform.system() == "Darwin" else "gguf"
        if backend == "mlx":
            return _MlxGemmaRunner(self.llm_config)
        if backend == "gguf":
            return _GgufGemmaRunner(self.llm_config)
        raise ValueError(f"Unknown LLM formatter backend: {self.llm_config.backend}")

    def _system_prompt(self) -> str:
        base_prompt = self.llm_config.prompt.strip()
        if not base_prompt:
            raise RuntimeError("LLM formatter prompt is empty.")
        schema = json.dumps(STRUCTURED_OUTPUT_SCHEMA, ensure_ascii=False)
        return (
            f"{base_prompt}\n\n"
            "出力は必ず次のJSON Schemaに一致するJSONオブジェクトのみとします。"
            "説明、Markdown、コードフェンス、余分なキーは出力しないでください。\n"
            f"{schema}"
        )

    @staticmethod
    def _build_user_prompt(text: str) -> str:
        return f"次のWhisper文字起こし結果を整形してください。\n\n{text}"

    def _parse_structured_output(self, output: str) -> str:
        cleaned = output.strip()
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
        cleaned = self._strip_json_fence(cleaned)

        payload = self._extract_json_object(cleaned)
        if payload is None:
            raise RuntimeError(
                f"LLM formatter returned invalid structured JSON.\nRaw output: {output!r}"
            )
        if not isinstance(payload, dict) or "formatted_text" not in payload:
            raise RuntimeError(
                f"LLM formatter JSON missing 'formatted_text'.\nRaw output: {output!r}"
            )
        formatted = payload["formatted_text"]
        if not isinstance(formatted, str):
            raise RuntimeError("LLM formatter formatted_text must be a string.")
        return formatted.strip()

    @staticmethod
    def _extract_json_object(text: str) -> dict | None:
        """Try to parse JSON, falling back to extracting the first {...} block."""
        candidates = [text]
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _strip_json_fence(text: str) -> str:
        if text.startswith("```json"):
            text = text.removeprefix("```json").strip()
        elif text.startswith("```"):
            text = text.removeprefix("```").strip()
        if text.endswith("```"):
            text = text.removesuffix("```").strip()
        return text


class _MlxGemmaRunner:
    """Gemma 4 E2B runner backed by mlx-vlm on macOS.

    All MLX calls are dispatched to a single dedicated thread so that the GPU
    stream initialised during load() is reused for every generate() call,
    regardless of which application thread invokes generate().
    """

    def __init__(self, config: Any) -> None:
        import concurrent.futures

        self.config = config
        self._model: Any | None = None
        self._processor: Any | None = None
        self._model_config: Any | None = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def load(self, on_status: StatusCallback | None = None) -> None:
        """Download and load the MLX model on the dedicated MLX thread."""

        self._executor.submit(self._load_sync, on_status).result()

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text on the dedicated MLX thread."""

        return self._executor.submit(self._generate_sync, system_prompt, user_prompt).result()

    def _load_sync(self, on_status: StatusCallback | None = None) -> None:
        if self._model is not None and self._processor is not None:
            return
        try:
            from mlx_vlm import load
        except ImportError as exc:  # pragma: no cover - covered by dependency absence only
            raise RuntimeError(
                "LLM formatter backend 'mlx' requires mlx-vlm. Install requirements-darwin.txt."
            ) from exc

        model_name = self.config.model
        if model_name == "auto":
            model_name = self.config.mlx_model
        local_model_dir = _resolve_hf_model_dir(model_name, "mlx", self.config, on_status)
        if on_status:
            on_status("モデルをメモリに読み込み中...")
        self._model, self._processor = load(local_model_dir)
        self._model_config = self._model.config

    def _generate_sync(self, system_prompt: str, user_prompt: str) -> str:
        self._load_sync()
        try:
            from mlx_vlm import generate
            from mlx_vlm.prompt_utils import apply_chat_template
        except ImportError as exc:  # pragma: no cover - covered by dependency absence only
            raise RuntimeError(
                "LLM formatter backend 'mlx' requires mlx-vlm. Install requirements-darwin.txt."
            ) from exc

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        formatted_prompt = apply_chat_template(self._processor, self._model_config, messages)
        result = generate(
            self._model,
            self._processor,
            formatted_prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            verbose=False,
        )
        return result.text if hasattr(result, "text") else str(result)


class _GgufGemmaRunner:
    """Gemma 4 E2B runner backed by llama-cpp-python for GGUF models."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self._llm: Any | None = None

    def load(self, on_status: StatusCallback | None = None) -> None:
        """Download and load the GGUF model."""

        self._load(on_status)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text with llama-cpp-python."""

        response = self._load().create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            response_format={
                "type": "json_object",
                "schema": STRUCTURED_OUTPUT_SCHEMA,
            },
        )
        return str(response["choices"][0]["message"]["content"])

    def _load(self, on_status: StatusCallback | None = None) -> Any:
        if self._llm is None:
            try:
                from llama_cpp import Llama
            except ImportError as exc:  # pragma: no cover - covered by dependency absence only
                raise RuntimeError(
                    "LLM formatter backend 'gguf' requires llama-cpp-python and "
                    "huggingface-hub. Install the platform requirements file."
                ) from exc

            model = self.config.model
            if model not in {"", "auto"} and model.endswith(".gguf"):
                self._llm = Llama(
                    model_path=model,
                    n_ctx=self.config.n_ctx,
                    n_gpu_layers=self.config.n_gpu_layers,
                    verbose=False,
                )
            else:
                repo_id = self.config.gguf_repo_id if model == "auto" else model
                if on_status:
                    on_status(f"モデルをダウンロード中: {repo_id}")
                self._llm = Llama.from_pretrained(
                    repo_id=repo_id,
                    filename=self.config.gguf_filename,
                    local_dir=str(_model_dir(repo_id, "gguf", self.config)),
                    local_dir_use_symlinks=False,
                    n_ctx=self.config.n_ctx,
                    n_gpu_layers=self.config.n_gpu_layers,
                    verbose=False,
                )
        return self._llm


def _resolve_hf_model_dir(
    model_id: str,
    backend: str,
    config: Any,
    on_status: StatusCallback | None = None,
) -> str:
    path = Path(model_id).expanduser()
    if path.exists():
        return str(path)
    local_dir = _model_dir(model_id, backend, config)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - covered by dependency absence only
        raise RuntimeError(
            "LLM formatter model download requires huggingface-hub. "
            "Install the platform requirements file."
        ) from exc

    if on_status:
        on_status(f"モデルをダウンロード中: {model_id}")

    download_kwargs: dict[str, Any] = {
        "repo_id": model_id,
        "local_dir": str(local_dir),
    }
    if on_status:
        download_kwargs["tqdm_class"] = _make_tqdm_class(on_status)
    snapshot_download(**download_kwargs)
    return str(local_dir)


def _make_tqdm_class(on_status: StatusCallback) -> type:
    """Return a tqdm subclass that routes file-level progress to on_status.

    Inheriting from tqdm.tqdm ensures all internal attributes (total, n, lock,
    etc.) are properly initialised; we only redirect display output to a
    StringIO sink and forward the current filename via on_status.
    """
    from io import StringIO

    from tqdm import tqdm

    class _StatusTqdm(tqdm):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("file", StringIO())
            super().__init__(*args, **kwargs)
            if self.desc:
                _notify(self.desc)

        def set_description(self, desc: Any = None, *args: Any, **kwargs: Any) -> None:
            super().set_description(desc, *args, **kwargs)
            if desc:
                _notify(desc)

    def _notify(desc: Any) -> None:
        filename = Path(str(desc)).name or str(desc)
        on_status(f"ダウンロード中: {filename}")

    return _StatusTqdm


def _prefer_http_progress_for_cli() -> None:
    """Prefer the regular HTTP downloader when CLI progress is requested."""

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    try:
        from huggingface_hub import constants
    except ImportError:  # pragma: no cover - handled by caller's import check
        return
    constants.HF_HUB_DISABLE_XET = os.environ["HF_HUB_DISABLE_XET"] == "1"


def _model_dir(model_id: str, backend: str, config: Any) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "__", model_id.strip("/"))
    path = Path(config.models_dir) / backend / safe_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_download_backend(llm_cfg: Any) -> str:
    backend = llm_cfg.backend.lower()
    if backend == "auto":
        return "mlx" if platform.system() == "Darwin" else "gguf"
    return backend


def _download_mlx_model(
    llm_cfg: Any,
    snapshot_download: Any,
    tqdm_cls: type | None,
    on_status: StatusCallback | None,
) -> None:
    model_id = llm_cfg.mlx_model if llm_cfg.model in ("", "auto") else llm_cfg.model
    local_dir = _model_dir(model_id, "mlx", llm_cfg)
    if on_status:
        on_status(f"モデルをダウンロード中: {model_id}")
    download_kwargs: dict[str, Any] = {
        "repo_id": model_id,
        "local_dir": str(local_dir),
    }
    if tqdm_cls is not None:
        download_kwargs["tqdm_class"] = tqdm_cls
    snapshot_download(**download_kwargs)


def _download_gguf_model(
    llm_cfg: Any,
    snapshot_download: Any,
    tqdm_cls: type | None,
    on_status: StatusCallback | None,
) -> None:
    repo_id = llm_cfg.gguf_repo_id if llm_cfg.model in ("", "auto") else llm_cfg.model
    local_dir = _model_dir(repo_id, "gguf", llm_cfg)
    if on_status:
        on_status(f"モデルをダウンロード中: {repo_id}")
    download_kwargs: dict[str, Any] = {
        "repo_id": repo_id,
        "local_dir": str(local_dir),
        "allow_patterns": [llm_cfg.gguf_filename],
    }
    if tqdm_cls is not None:
        download_kwargs["tqdm_class"] = tqdm_cls
    snapshot_download(**download_kwargs)


def download_llm_model(
    config: Any,
    on_status: StatusCallback | None = None,
    show_progress: bool = False,
) -> None:
    """Download the LLM model files without loading them into memory.

    Reads backend / model settings from *config* (a FormatterConfig or its
    .llm sub-config) and fetches the required files from Hugging Face into
    the configured models_dir.  Safe to call when files are already present
    — huggingface_hub will skip files that match the cached etag.

    Set *show_progress* for the standalone CLI so Hugging Face's normal tqdm
    progress bars remain visible.  Application startup keeps this disabled and
    uses *on_status* for quiet UI-friendly status messages.
    """
    from src.config import FormatterConfig

    llm_cfg = config.llm if isinstance(config, FormatterConfig) else config

    backend = _resolve_download_backend(llm_cfg)

    if show_progress:
        _prefer_http_progress_for_cli()

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "モデルのダウンロードには huggingface-hub が必要です。"
            "requirements ファイルをインストールしてください。"
        ) from exc

    tqdm_cls = _make_tqdm_class(on_status) if on_status and not show_progress else None

    if backend == "mlx":
        _download_mlx_model(llm_cfg, snapshot_download, tqdm_cls, on_status)
    elif backend == "gguf":
        _download_gguf_model(llm_cfg, snapshot_download, tqdm_cls, on_status)
