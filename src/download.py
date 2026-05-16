"""Download the LLM model if formatter.backend is 'llm' in config.yaml."""

from __future__ import annotations


def main() -> None:
    from src.config import load_config

    config = load_config("config.yaml")

    if config.formatter.backend != "llm":
        print("formatter.backend が 'llm' でないためスキップします。")
        return

    from src.formatter.backends.llm import download_llm_model

    print("LLMモデルをダウンロードします（初回のみ・数分かかる場合があります）...")

    def on_status(msg: str) -> None:
        print(f"  {msg}", flush=True)

    download_llm_model(config.formatter, on_status=on_status)
    print("完了。")


if __name__ == "__main__":
    main()
