"""Download the LLM model if formatter.backend is 'llm' in config.yaml."""

from __future__ import annotations


def main() -> None:
    from src.config import load_config

    config = load_config("config.yaml")

    if config.formatter.backend != "llm":
        print("skip model download because formatter.backend is not 'llm'.")
        return

    from src.formatter.backends.llm import download_llm_model

    print("download LLM model（first time only/this tooks few minutes）...")

    def on_status(msg: str) -> None:
        print(f"  {msg}", flush=True)

    download_llm_model(config.formatter, on_status=on_status, show_progress=True)
    print("complete。")


if __name__ == "__main__":
    main()
