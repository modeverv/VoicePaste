from __future__ import annotations

import pytest

from src.config import FormatterConfig
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


def test_llm_formatter_stub_raises() -> None:
    formatter = LLMFormatter(FormatterConfig(backend="llm"))

    with pytest.raises(NotImplementedError, match="not yet implemented"):
        formatter.format("テスト")
