from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from src.clipboard import copy_to_clipboard


def test_copy_to_clipboard_macos() -> None:
    with patch("platform.system", return_value="Darwin"), patch("subprocess.run") as mock_run:
        copy_to_clipboard("テスト")

    mock_run.assert_called_once_with("pbcopy", input="テスト".encode(), check=True)


def test_copy_to_clipboard_linux() -> None:
    with patch("platform.system", return_value="Linux"), patch("subprocess.run") as mock_run:
        copy_to_clipboard("hello")

    mock_run.assert_called_once_with(
        ["xclip", "-selection", "clipboard"],
        input=b"hello",
        check=True,
    )


def test_copy_to_clipboard_windows() -> None:
    with patch("platform.system", return_value="Windows"), patch("subprocess.run") as mock_run:
        copy_to_clipboard("hello")

    mock_run.assert_called_once_with("clip", input=b"hello", check=True, shell=True)


def test_copy_to_clipboard_unsupported_os() -> None:
    with (
        patch("platform.system", return_value="Plan9"),
        pytest.raises(RuntimeError, match="Unsupported OS"),
    ):
        copy_to_clipboard("hello")


def test_copy_to_clipboard_wraps_command_failure() -> None:
    with (
        patch("platform.system", return_value="Darwin"),
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "pbcopy")),
        pytest.raises(RuntimeError, match="Failed to write"),
    ):
        copy_to_clipboard("hello")
