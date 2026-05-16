"""Global push-to-talk hotkey listener."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class HotkeyListener:
    """Listen for a global hotkey and emit press/release callbacks."""

    def __init__(
        self,
        hotkey: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None],
    ) -> None:
        """Create a hotkey listener."""

        self.hotkey = hotkey
        self.on_press_callback = on_press
        self.on_release_callback = on_release
        self._pressed: set[str] = set()
        self._required = self._parse_hotkey(hotkey)
        self._active = False
        self._listener: Any | None = None

    def start(self) -> None:
        """Start listening in the background."""

        from pynput import keyboard

        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()

    def stop(self) -> None:
        """Stop listening."""

        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def join(self) -> None:
        """Block until the listener exits."""

        if self._listener is not None:
            self._listener.join()

    def _on_press(self, key: Any) -> None:
        token = self._normalize_key(key)
        self._pressed.add(token)
        if not self._active and self._required.issubset(self._pressed):
            self._active = True
            self.on_press_callback()

    def _on_release(self, key: Any) -> None:
        token = self._normalize_key(key)
        self._pressed.discard(token)
        if self._active and token in self._required:
            self._active = False
            self.on_release_callback()

    @staticmethod
    def _parse_hotkey(hotkey: str) -> set[str]:
        return {part.strip().lower().strip("<>") for part in hotkey.split("+") if part.strip()}

    @staticmethod
    def _normalize_key(key: Any) -> str:
        char = getattr(key, "char", None)
        if char:
            if char == " ":
                return "space"
            return str(char).lower()
        name = getattr(key, "name", None)
        if name:
            normalized = str(name).lower()
            aliases = {"cmd_l": "cmd", "cmd_r": "cmd", "shift_l": "shift", "shift_r": "shift"}
            return aliases.get(normalized, normalized)
        text = str(key).replace("Key.", "").lower()
        aliases = {"cmd_l": "cmd", "cmd_r": "cmd", "shift_l": "shift", "shift_r": "shift"}
        return aliases.get(text, text)
