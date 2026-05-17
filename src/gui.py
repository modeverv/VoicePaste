"""Tkinter GUI entry point for VoicePaste."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from typing import Any

from src.config import load_config
from src.hotkey import HotkeyListener
from src.main import State, VoicePasteApp
from src.mic_level import MicLevelMonitor, format_mic_level


@dataclass(frozen=True)
class GuiViewModel:
    """Presentation data for the VoicePaste floating GUI."""

    status: str
    status_color: str
    body: str
    body_color: str
    body_italic: bool = False

    @classmethod
    def from_app(cls, app: VoicePasteApp) -> GuiViewModel:
        """Build GUI presentation data from the current application state."""

        with app._lock:
            state = app.state
            preview = app.preview_text
            final = app.final_text
            error = app.error_text
            hotkey = app.config.hotkey

        if state == State.LOADING:
            return cls("○ Loading model...", "#b7791f", final, "#718096")
        if state == State.RECORDING:
            return cls("● RECORDING...", "#e53e3e", preview, "#718096", body_italic=True)
        if state == State.PROCESSING:
            return cls("⚙ PROCESSING...", "#b7791f", preview, "#718096", body_italic=True)
        if state == State.DONE:
            return cls("✓ Copied to clipboard", "#2f855a", final, "#1a202c")
        if state == State.ERROR:
            return cls("✗ ERROR", "#e53e3e", error, "#e53e3e")
        return cls(f"○ Ready  [{hotkey}]", "#718096", final, "#718096")


class VoicePasteGui:
    """Small always-on-top Tkinter window for VoicePaste status and text."""

    def __init__(self, app: VoicePasteApp, root: Any | None = None, poll_ms: int = 125) -> None:
        """Create the GUI runner.

        Args:
            app: VoicePaste application coordinator.
            root: Optional Tk root for tests or custom embedding.
            poll_ms: UI refresh interval in milliseconds.
        """

        self.app = app
        self.root = root
        self.poll_ms = poll_ms
        self.listener: HotkeyListener | None = None
        self._level_monitor = MicLevelMonitor(
            device=app.config.input_device,
            input_sample_rate=app.config.input_sample_rate,
            update_ms=app.config.mic_meter_update_ms,
        )
        self._closed = False
        self._status_label: Any | None = None
        self._body_label: Any | None = None
        self._level_label: Any | None = None

    def run(self) -> None:
        """Run the Tkinter GUI and global hotkey listener."""

        import tkinter as tk
        from tkinter import font

        self._load_before_tk()
        if self.root is None:
            self.root = tk.Tk()
        self._configure_root()

        container = tk.Frame(self.root, bg="#f7fafc", padx=16, pady=14)
        container.pack(fill="both", expand=True)

        self._status_label = tk.Label(
            container,
            text="",
            bg="#f7fafc",
            anchor="w",
            font=("TkDefaultFont", 12, "bold"),
        )
        self._status_label.pack(fill="x", pady=(0, 8))

        body_font = font.Font(family="TkDefaultFont", size=12)
        self._body_label = tk.Label(
            container,
            text="",
            bg="#f7fafc",
            fg="#718096",
            anchor="nw",
            justify="left",
            wraplength=320,
            height=4,
            font=body_font,
        )
        self._body_label.pack(fill="both", expand=True)
        self._body_label._normal_font = body_font
        self._body_label._italic_font = body_font.copy()
        self._body_label._italic_font.configure(slant="italic")

        self._level_label = tk.Label(
            container,
            text="RMS --.- dBFS  Peak --.- dBFS",
            bg="#f7fafc",
            fg="#4a5568",
            anchor="e",
            font=("TkDefaultFont", 10),
        )
        self._level_label.pack(fill="x", pady=(8, 0))

        self._ensure_level_monitor()
        self._start_hotkey()
        self._refresh()
        self.root.mainloop()

    def close(self) -> None:
        """Stop the listener and close the window."""

        self._closed = True
        self._level_monitor.stop()
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
        if self.root is not None:
            self.root.destroy()

    def _configure_root(self) -> None:
        self.root.title("VoicePaste")
        self.root.geometry("420x190")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _load_before_tk(self) -> None:
        try:
            with self.app._lock:
                self.app.state = State.LOADING
            print("Loading model before opening GUI...", flush=True)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.app.load()
            with self.app._lock:
                self.app.state = State.IDLE
            print("Model loaded. Opening GUI...", flush=True)
        except Exception as exc:  # pragma: no cover - defensive GUI guard
            self.app._set_error(exc)

    def _start_hotkey(self) -> None:
        if self.app.state == State.ERROR:
            return
        self.listener = self.app.hotkey_factory(
            self.app.config.hotkey,
            self._start_recording,
            self._stop_recording,
        )
        self.listener.start()

    def _start_recording(self) -> None:
        self._level_monitor.stop()
        self.app.start_recording()

    def _stop_recording(self) -> None:
        self.app.stop_recording()
        self._ensure_level_monitor()

    def _ensure_level_monitor(self) -> None:
        if self.app.state == State.RECORDING or self._level_monitor.is_running:
            return
        try:
            self._level_monitor.start()
        except Exception:
            if self._level_label is not None:
                self._level_label.configure(text="RMS --.- dBFS  Peak --.- dBFS")

    def _refresh(self) -> None:
        if self._closed:
            return
        self._render_once()
        self.root.after(self.poll_ms, self._refresh)

    def _render_once(self) -> None:
        vm = GuiViewModel.from_app(self.app)
        if self._status_label is not None:
            self._status_label.configure(text=vm.status, fg=vm.status_color)
        if self._body_label is not None:
            text = f"~ {vm.body}" if vm.body_italic and vm.body else vm.body
            font_key = "_italic_font" if vm.body_italic else "_normal_font"
            self._body_label.configure(
                text=text,
                fg=vm.body_color,
                font=getattr(self._body_label, font_key),
            )
        if self._level_label is not None:
            level = (
                self.app.latest_mic_level
                if self.app.state == State.RECORDING
                else self._level_monitor.latest_level
            )
            self._level_label.configure(text=format_mic_level(level))
        self.root.attributes("-topmost", True)


def main() -> None:
    """Run VoicePaste using the floating GUI."""

    from src.microphone import select_microphone

    app = VoicePasteApp(select_microphone(load_config("config.yaml")))
    VoicePasteGui(app).run()


if __name__ == "__main__":
    main()
