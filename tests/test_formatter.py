from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from src.config import FormatterConfig, LLMFormatterConfig
from src.formatter import PostFormatter
from src.formatter.backends.llm import LLMFormatter
from src.formatter.backends.rule import RuleFormatter


def test_post_formatter_factory_rule() -> None:
    formatter = PostFormatter.from_config(FormatterConfig(backend="rule"))

    assert isinstance(formatter, RuleFormatter)


def test_post_formatter_factory_llm() -> None:
    formatter = PostFormatter.from_config(FormatterConfig(backend="llm"))

    assert isinstance(formatter, LLMFormatter)


def test_post_formatter_factory_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown formatter backend"):
        PostFormatter.from_config(FormatterConfig(backend="unknown"))


def test_rule_formatter_removes_fillers_and_adds_period() -> None:
    formatter = RuleFormatter(FormatterConfig(fillers=["えっと", "なんか"]))

    assert formatter.format("えっとこれはなんかテストです") == "これはテストです。"


def test_rule_formatter_can_disable_fillers_and_punctuation() -> None:
    formatter = RuleFormatter(
        FormatterConfig(remove_fillers=False, add_punctuation=False, fillers=["えっと"])
    )

    assert formatter.format("  えっと テスト  ") == "えっと テスト"


def test_rule_formatter_normalizes_repeated_punctuation() -> None:
    formatter = RuleFormatter(FormatterConfig())

    assert formatter.format("これはテストです。。") == "これはテストです。"


def test_rule_formatter_inserts_comma_for_long_sentence() -> None:
    formatter = RuleFormatter(FormatterConfig())
    text = (
        "これはとても長い文章なので音声入力の結果として句読点がない場合でも"
        "読みやすくするために自然な位置へ補完します"
    )

    formatted = formatter.format(text)

    assert "、" in formatted
    assert formatted.endswith("。")
    assert formatted.replace("、", "").removesuffix("。") == text


class FakeRunner:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls: list[tuple[str, str]] = []

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.output


def test_llm_formatter_uses_runner_and_parses_structured_output() -> None:
    runner = FakeRunner('{"formatted_text": "これはテストです。"}')
    formatter = LLMFormatter(FormatterConfig(backend="llm"))
    formatter._runner = runner

    assert formatter.format("  えっとこれはテストです  ") == "これはテストです。"
    assert "formatted_text" in runner.calls[0][0]
    assert "Whisper文字起こし結果" in runner.calls[0][1]


def test_llm_formatter_uses_prompt_from_config() -> None:
    runner = FakeRunner('{"formatted_text": "これはテストです。"}')
    formatter = LLMFormatter(
        FormatterConfig(
            backend="llm",
            llm=LLMFormatterConfig(prompt="config側プロンプトです。"),
        )
    )
    formatter._runner = runner

    assert formatter.format("えっとこれはテストです") == "これはテストです。"
    assert runner.calls[0][0].startswith("config側プロンプトです。")


def test_llm_formatter_errors_when_prompt_is_empty() -> None:
    formatter = LLMFormatter(
        FormatterConfig(
            backend="llm",
            llm=LLMFormatterConfig(prompt=""),
        )
    )

    with pytest.raises(RuntimeError, match="prompt is empty"):
        formatter.format("テスト")


def test_llm_formatter_allows_json_code_fence() -> None:
    runner = FakeRunner('```json\n{"formatted_text": "これはテストです。"}\n```')
    formatter = LLMFormatter(FormatterConfig(backend="llm"))
    formatter._runner = runner

    assert formatter.format("えっとこれはテストです") == "これはテストです。"


def test_llm_formatter_rejects_unstructured_output() -> None:
    runner = FakeRunner("これはテストです。")
    formatter = LLMFormatter(FormatterConfig(backend="llm"))
    formatter._runner = runner

    with pytest.raises(RuntimeError, match="invalid structured JSON"):
        formatter.format("えっとこれはテストです")


def test_llm_formatter_accepts_extra_json_keys() -> None:
    runner = FakeRunner('{"formatted_text": "これはテストです。", "notes": "removed filler"}')
    formatter = LLMFormatter(FormatterConfig(backend="llm"))
    formatter._runner = runner

    assert formatter.format("えっとこれはテストです") == "これはテストです。"


def test_llm_formatter_empty_input_skips_runner() -> None:
    runner = FakeRunner("should not be used")
    formatter = LLMFormatter(FormatterConfig(backend="llm"))
    formatter._runner = runner

    assert formatter.format("   ") == ""
    assert runner.calls == []


def test_llm_formatter_rejects_unknown_backend() -> None:
    formatter = LLMFormatter(
        FormatterConfig(backend="llm", llm=LLMFormatterConfig(backend="unknown"))
    )

    with pytest.raises(ValueError, match="Unknown LLM formatter backend"):
        formatter.format("テスト")


def test_llm_formatter_auto_backend_uses_mlx_on_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    formatter = LLMFormatter(FormatterConfig(backend="llm"))

    monkeypatch.setattr("platform.system", lambda: "Darwin")

    assert formatter._create_runner().__class__.__name__ == "_MlxGemmaRunner"


def test_llm_formatter_auto_backend_uses_gguf_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    formatter = LLMFormatter(FormatterConfig(backend="llm"))

    monkeypatch.setattr("platform.system", lambda: "Linux")

    assert formatter._create_runner().__class__.__name__ == "_GgufGemmaRunner"


def test_mlx_runner_loads_configured_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, Any] = {}
    fake_model = types.SimpleNamespace(config=types.SimpleNamespace())
    fake_mlx_vlm = types.ModuleType("mlx_vlm")
    fake_prompt_utils = types.ModuleType("mlx_vlm.prompt_utils")
    fake_huggingface_hub = types.ModuleType("huggingface_hub")

    def fake_load(model_name: str) -> tuple[Any, Any]:
        calls["model_name"] = model_name
        return fake_model, object()

    def fake_generate(*args: Any, **kwargs: Any) -> str:
        calls["generate_kwargs"] = kwargs
        return '{"formatted_text": "整形済みです。"}'

    def fake_apply_chat_template(*args: Any, **kwargs: Any) -> str:
        calls["template_args"] = args
        return "templated prompt"

    def fake_snapshot_download(**kwargs: Any) -> str:
        calls["snapshot_download"] = kwargs
        return str(kwargs["local_dir"])

    fake_mlx_vlm.load = fake_load
    fake_mlx_vlm.generate = fake_generate
    fake_prompt_utils.apply_chat_template = fake_apply_chat_template
    fake_huggingface_hub.snapshot_download = fake_snapshot_download
    monkeypatch.setitem(sys.modules, "mlx_vlm", fake_mlx_vlm)
    monkeypatch.setitem(sys.modules, "mlx_vlm.prompt_utils", fake_prompt_utils)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_huggingface_hub)

    formatter = LLMFormatter(
        FormatterConfig(
            backend="llm",
            llm=LLMFormatterConfig(
                backend="mlx",
                mlx_model="mlx-community/test-model",
                models_dir=str(tmp_path),
            ),
        )
    )

    assert formatter.format("えっとテスト") == "整形済みです。"
    assert calls["snapshot_download"]["repo_id"] == "mlx-community/test-model"
    expected_dir = str(tmp_path / "mlx" / "mlx-community__test-model")
    assert calls["snapshot_download"]["local_dir"] == expected_dir
    assert calls["model_name"] == expected_dir
    assert calls["generate_kwargs"]["temperature"] == 0.0


def test_gguf_runner_loads_configured_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: dict[str, Any] = {}
    fake_llama_cpp = types.ModuleType("llama_cpp")

    class FakeLlama:
        @classmethod
        def from_pretrained(cls, **kwargs: Any) -> FakeLlama:
            calls["from_pretrained"] = kwargs
            return cls()

        def create_chat_completion(self, **kwargs: Any) -> dict[str, Any]:
            calls["chat"] = kwargs
            return {
                "choices": [{"message": {"content": '{"formatted_text": "これはテストです。"}'}}]
            }

    fake_llama_cpp.Llama = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama_cpp)

    formatter = LLMFormatter(
        FormatterConfig(
            backend="llm",
            llm=LLMFormatterConfig(
                backend="gguf",
                gguf_repo_id="example/gemma-gguf",
                gguf_filename="*Q4_K_M.gguf",
                models_dir=str(tmp_path),
            ),
        )
    )

    assert formatter.format("えっとこれはテストです") == "これはテストです。"
    assert calls["from_pretrained"]["repo_id"] == "example/gemma-gguf"
    assert calls["from_pretrained"]["filename"] == "*Q4_K_M.gguf"
    assert calls["from_pretrained"]["local_dir"] == str(tmp_path / "gguf" / "example__gemma-gguf")
    assert calls["from_pretrained"]["local_dir_use_symlinks"] is False
    assert calls["chat"]["temperature"] == 0.0
    assert calls["chat"]["response_format"]["schema"]["required"] == ["formatted_text"]


def test_llm_formatter_load_preloads_runner() -> None:
    class LoadableRunner(FakeRunner):
        def __init__(self) -> None:
            super().__init__('{"formatted_text": "unused"}')
            self.load_called = False

        def load(self) -> None:
            self.load_called = True

    runner = LoadableRunner()
    formatter = LLMFormatter(FormatterConfig(backend="llm"))
    formatter._runner = runner

    formatter.load()

    assert runner.load_called is True
