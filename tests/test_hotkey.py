from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.hotkey import HotkeyListener


class FakeKey:
    def __init__(self, name: str | None = None, char: str | None = None) -> None:
        self.name = name
        self.char = char


class FakeListener:
    def __init__(self, on_press: object, on_release: object) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.start = Mock()
        self.stop = Mock()
        self.join = Mock()


def test_hotkey_press_and_release_callbacks_once() -> None:
    on_press = Mock()
    on_release = Mock()
    listener = HotkeyListener("<cmd>+<shift>+space", on_press, on_release)

    listener._on_press(FakeKey(name="cmd"))
    listener._on_press(FakeKey(name="shift"))
    listener._on_press(FakeKey(char=" "))
    listener._on_press(FakeKey(char=" "))
    listener._on_release(FakeKey(name="shift"))

    on_press.assert_called_once()
    on_release.assert_called_once()


def test_hotkey_start_uses_pynput_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[FakeListener] = []

    def factory(on_press: object, on_release: object) -> FakeListener:
        listener = FakeListener(on_press, on_release)
        created.append(listener)
        return listener

    monkeypatch.setitem(
        sys.modules,
        "pynput",
        SimpleNamespace(keyboard=SimpleNamespace(Listener=factory)),
    )
    listener = HotkeyListener("<cmd>+space", Mock(), Mock())

    listener.start()
    listener.stop()
    listener.join()

    assert len(created) == 1
    created[0].start.assert_called_once()
    created[0].stop.assert_called_once()
