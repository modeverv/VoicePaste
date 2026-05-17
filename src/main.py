"""VoicePaste application entry point and TUI integration."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from enum import Enum, auto
from io import StringIO
from typing import Any

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from src.audio_debug import audio_rms, is_silent, save_wav
from src.clipboard import copy_to_clipboard
from src.config import Config, load_config
from src.formatter import PostFormatter
from src.hotkey import HotkeyListener
from src.mic_level import MicLevel
from src.recorder import AudioArray, Recorder
from src.transcriber import Transcriber


class State(Enum):
    """Application state."""

    LOADING = auto()
    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()
    DONE = auto()
    ERROR = auto()


class VoicePasteApp:
    """Coordinate recording, transcription, formatting, clipboard, and TUI state."""

    def __init__(
        self,
        config: Config,
        recorder_factory: Callable[[queue.Queue[AudioArray]], Recorder] | None = None,
        transcriber: Transcriber | None = None,
        formatter: PostFormatter | None = None,
        clipboard_writer: Callable[[str], None] = copy_to_clipboard,
        hotkey_factory: Callable[[str, Callable[[], None], Callable[[], None]], HotkeyListener]
        | None = None,
    ) -> None:
        """Create the application coordinator with injectable dependencies."""

        self.config = config
        self.chunk_queue: queue.Queue[AudioArray | None] = queue.Queue()
        self.recorder_factory = recorder_factory or self._default_recorder_factory
        self.transcriber = transcriber or Transcriber(config)
        self.formatter = formatter or PostFormatter.from_config(config.formatter)
        self.clipboard_writer = clipboard_writer
        self.hotkey_factory = hotkey_factory or HotkeyListener
        self.state = State.IDLE
        self.preview_text = ""
        self.final_text = ""
        self.error_text = ""
        self._recorder: Recorder | None = None
        self._chunk_thread: threading.Thread | None = None
        self._final_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def load(self) -> None:
        """Load models before the interactive UI starts."""

        self.transcriber.load()
        formatter_load = getattr(self.formatter, "load", None)
        if callable(formatter_load):
            formatter_load()

    def start_recording(self) -> None:
        """Start a push-to-talk recording session."""

        with self._lock:
            if self.state == State.RECORDING:
                return
            self.state = State.RECORDING
            self.preview_text = ""
            self.error_text = ""
            self.chunk_queue = queue.Queue()
            self._recorder = self.recorder_factory(self.chunk_queue)
            self._chunk_thread = threading.Thread(target=self._chunk_worker, daemon=True)
            self._chunk_thread.start()
            self._recorder.start()

    def stop_recording(self) -> None:
        """Stop recording and start final transcription."""

        with self._lock:
            if self.state != State.RECORDING or self._recorder is None:
                return
            self.state = State.PROCESSING
            recorder = self._recorder
            self._recorder = None
        try:
            full_audio = recorder.stop()
            self.chunk_queue.put(None)
            self._final_thread = threading.Thread(target=self._final_worker, args=(full_audio,))
            self._final_thread.start()
        except Exception as exc:  # pragma: no cover - defensive UI guard
            self._set_error(exc)

    def wait_for_processing(self, timeout: float | None = None) -> None:
        """Wait for the final processing thread, if any."""

        if self._final_thread is not None:
            self._final_thread.join(timeout=timeout)

    @property
    def latest_mic_level(self) -> MicLevel:
        """Return the latest level from the active recorder, if any."""

        with self._lock:
            recorder = self._recorder
        if recorder is None:
            return MicLevel()
        return recorder.latest_level

    def render(self) -> Panel:
        """Render the current TUI panel."""

        with self._lock:
            state = self.state
            preview = self.preview_text
            final = self.final_text
            error = self.error_text
        status = self._status_text(state)
        body: list[Any] = [Text("VoicePaste", style="bold"), Text(""), status, Text("")]
        if state in {State.RECORDING, State.PROCESSING} and preview:
            body.append(Text(f"~ {preview}", style="dim italic"))
        elif state == State.ERROR:
            body.append(Text(error, style="red"))
        elif final:
            body.append(Text(final, style="green"))
        return Panel(Group(*body), border_style=self._border_style(state))

    def run(self) -> None:
        """Run the TUI and global hotkey listener."""

        listener: HotkeyListener | None = None
        with self._lock:
            self.state = State.LOADING
        try:
            with Live(self.render(), refresh_per_second=4, screen=True) as live:
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    self.load()
                with self._lock:
                    self.state = State.IDLE
                live.update(self.render())
                listener = self.hotkey_factory(
                    self.config.hotkey,
                    self.start_recording,
                    self.stop_recording,
                )
                listener.start()
                live.refresh_per_second = 8
                while True:
                    live.update(self.render())
                    time.sleep(0.125)
        except KeyboardInterrupt:
            pass
        finally:
            if listener is not None:
                listener.stop()

    def _chunk_worker(self) -> None:
        while True:
            audio = self.chunk_queue.get()
            if audio is None:
                return
            try:
                text = self.transcriber.transcribe_chunk(audio)
            except Exception as exc:  # pragma: no cover - defensive UI guard
                self._set_error(exc)
                return
            with self._lock:
                if text:
                    self.preview_text = text

    def _final_worker(self, full_audio: AudioArray) -> None:
        try:
            save_wav(full_audio, self.config.debug_audio_path, self.config.sample_rate)
            if is_silent(full_audio):
                raise RuntimeError(
                    "Recorded audio is silent "
                    f"(RMS={audio_rms(full_audio):.8f}). "
                    f"Saved debug WAV: {self.config.debug_audio_path}. "
                    "Check macOS Microphone permission for the app running VoicePaste "
                    "and verify the input device."
                )
            raw_text = self.transcriber.transcribe(full_audio)
            formatted = self.formatter.format(raw_text)
            self.clipboard_writer(formatted)
            with self._lock:
                self.final_text = formatted
                self.preview_text = ""
                self.state = State.DONE
            time.sleep(0.5)
            with self._lock:
                if self.state == State.DONE:
                    self.state = State.IDLE
        except Exception as exc:
            self._set_error(exc)

    def _set_error(self, exc: Exception) -> None:
        with self._lock:
            self.error_text = str(exc)
            self.state = State.ERROR

    def _default_recorder_factory(self, chunk_queue: queue.Queue[AudioArray]) -> Recorder:
        return Recorder(
            sample_rate=self.config.sample_rate,
            input_sample_rate=self.config.input_sample_rate,
            chunk_seconds=self.config.chunk_seconds,
            chunk_queue=chunk_queue,
            device=self.config.input_device,
        )

    def _status_text(self, state: State) -> Text:
        if state == State.LOADING:
            return Text("○ Loading model...", style="yellow")
        if state == State.IDLE:
            return Text(f"○ Ready  [{self.config.hotkey}]", style="dim")
        if state == State.RECORDING:
            return Text("● RECORDING...", style="red")
        if state == State.PROCESSING:
            return Text("⚙ PROCESSING...", style="yellow")
        if state == State.DONE:
            return Text("✓ Copied to clipboard", style="green")
        return Text("✗ ERROR", style="red")

    @staticmethod
    def _border_style(state: State) -> str:
        if state == State.RECORDING:
            return "red"
        if state == State.PROCESSING:
            return "yellow"
        if state == State.DONE:
            return "green"
        if state == State.ERROR:
            return "red"
        if state == State.LOADING:
            return "yellow"
        return "dim"


def main() -> None:
    """Run VoicePaste using config.yaml."""

    from src.microphone import select_microphone

    app = VoicePasteApp(select_microphone(load_config("config.yaml")))
    app.run()


if __name__ == "__main__":
    main()
