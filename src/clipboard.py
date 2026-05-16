"""Cross-platform clipboard writing."""

from __future__ import annotations

import platform
import subprocess


def copy_to_clipboard(text: str) -> None:
    """Write text to the OS clipboard.

    Args:
        text: Text to copy.

    Raises:
        RuntimeError: If the current OS is unsupported or the clipboard command fails.
    """

    system = platform.system()
    data = text.encode("utf-8")
    try:
        if system == "Darwin":
            subprocess.run("pbcopy", input=data, check=True)
        elif system == "Linux":
            subprocess.run(["xclip", "-selection", "clipboard"], input=data, check=True)
        elif system == "Windows":
            subprocess.run("clip", input=data, check=True, shell=True)
        else:
            raise RuntimeError(f"Unsupported OS: {system}")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Failed to write to clipboard.") from exc
