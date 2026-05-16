"""Local LLM formatter backend."""

from __future__ import annotations

import json
import platform
import re
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


class _LLMRunner(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate a structured JSON string from prompts."""


class LLMFormatter(PostFormatter):
    """Format final Whisper text with a local Gemma 4 E2B model."""

    def __init__(self, config: FormatterConfig) -> None:
        """Initialize the local LLM formatter from formatter config."""

        self.config = config
        self.llm_config = config.llm
        self._runner: _LLMRunner | None = None

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
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM formatter returned invalid structured JSON.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("LLM formatter JSON must be an object.")
        if set(payload) != {"formatted_text"}:
            raise RuntimeError("LLM formatter JSON must contain only formatted_text.")
        formatted = payload["formatted_text"]
        if not isinstance(formatted, str):
            raise RuntimeError("LLM formatter formatted_text must be a string.")
        return formatted.strip()

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
    """Gemma 4 E2B runner backed by mlx-vlm on macOS."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self._model: Any | None = None
        self._processor: Any | None = None
        self._model_config: Any | None = None

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text with mlx-vlm."""

        model, processor, model_config = self._load()
        try:
            from mlx_vlm import generate
            from mlx_vlm.prompt_utils import apply_chat_template
        except ImportError as exc:  # pragma: no cover - covered by dependency absence only
            raise RuntimeError(
                "LLM formatter backend 'mlx' requires mlx-vlm. Install requirements-darwin.txt."
            ) from exc

        prompt = f"{system_prompt}\n\n{user_prompt}"
        formatted_prompt = apply_chat_template(processor, model_config, prompt)
        result = generate(
            model,
            processor,
            formatted_prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            verbose=False,
        )
        return str(result)

    def _load(self) -> tuple[Any, Any, Any]:
        if self._model is None or self._processor is None:
            try:
                from mlx_vlm import load
            except ImportError as exc:  # pragma: no cover - covered by dependency absence only
                raise RuntimeError(
                    "LLM formatter backend 'mlx' requires mlx-vlm. Install requirements-darwin.txt."
                ) from exc

            model_name = self.config.model
            if model_name == "auto":
                model_name = self.config.mlx_model
            self._model, self._processor = load(model_name)
            self._model_config = self._model.config
        return self._model, self._processor, self._model_config


class _GgufGemmaRunner:
    """Gemma 4 E2B runner backed by llama-cpp-python for GGUF models."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self._llm: Any | None = None

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

    def _load(self) -> Any:
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
                self._llm = Llama.from_pretrained(
                    repo_id=self.config.gguf_repo_id if model == "auto" else model,
                    filename=self.config.gguf_filename,
                    n_ctx=self.config.n_ctx,
                    n_gpu_layers=self.config.n_gpu_layers,
                    verbose=False,
                )
        return self._llm
