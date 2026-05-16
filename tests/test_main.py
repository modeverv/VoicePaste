from __future__ import annotations

import queue
import wave
from pathlib import Path
from unittest.mock import Mock

import numpy as np

from src.config import Config
from src.main import State, VoicePasteApp
from src.recorder import AudioArray


class FakeRecorder:
    def __init__(self, chunk_queue: queue.Queue[AudioArray | None]) -> None:
        self.chunk_queue = chunk_queue
        self.start = Mock()
        self.stop = Mock(return_value=np.ones(4, dtype=np.float32))


class FakeTranscriber:
    def __init__(self) -> None:
        self.load = Mock()
        self.transcribe = Mock(return_value="えっとこれはテストです")
        self.transcribe_chunk = Mock(return_value="えっとこれは")


class FakeFormatter:
    def __init__(self) -> None:
        self.load = Mock()

    def format(self, text: str) -> str:
        return text.replace("えっと", "") + "。"


def test_app_recording_to_clipboard_flow(tmp_path: Path) -> None:
    recorder_holder: dict[str, FakeRecorder] = {}

    def recorder_factory(chunk_queue: queue.Queue[AudioArray | None]) -> FakeRecorder:
        recorder = FakeRecorder(chunk_queue)
        recorder_holder["recorder"] = recorder
        return recorder

    clipboard = Mock()
    debug_path = tmp_path / "last_recording.wav"
    app = VoicePasteApp(
        Config(debug_audio_path=str(debug_path)),
        recorder_factory=recorder_factory,
        transcriber=FakeTranscriber(),
        formatter=FakeFormatter(),
        clipboard_writer=clipboard,
    )

    app.start_recording()
    app.chunk_queue.put(np.ones(3, dtype=np.float32))
    app.stop_recording()
    app.wait_for_processing(timeout=2)

    recorder_holder["recorder"].start.assert_called_once()
    recorder_holder["recorder"].stop.assert_called_once()
    clipboard.assert_called_once_with("これはテストです。")
    assert app.final_text == "これはテストです。"
    assert app.state in {State.DONE, State.IDLE}
    with wave.open(str(debug_path), "rb") as wav:
        assert wav.getframerate() == 16000
        assert wav.getnframes() == 4


def test_app_sets_error_when_final_processing_fails() -> None:
    transcriber = FakeTranscriber()
    transcriber.transcribe.side_effect = RuntimeError("boom")
    app = VoicePasteApp(Config(), transcriber=transcriber, clipboard_writer=Mock())

    app._final_worker(np.ones(4, dtype=np.float32))

    assert app.state == State.ERROR
    assert app.error_text == "boom"


def test_app_sets_error_for_silent_audio(tmp_path: Path) -> None:
    debug_path = tmp_path / "silent.wav"
    transcriber = FakeTranscriber()
    app = VoicePasteApp(
        Config(debug_audio_path=str(debug_path)),
        transcriber=transcriber,
        clipboard_writer=Mock(),
    )

    app._final_worker(np.zeros(4, dtype=np.float32))

    assert app.state == State.ERROR
    assert "Recorded audio is silent" in app.error_text
    assert debug_path.exists()
    transcriber.transcribe.assert_not_called()


def test_render_includes_ready_status() -> None:
    app = VoicePasteApp(Config(), transcriber=FakeTranscriber(), clipboard_writer=Mock())

    rendered = app.render()

    assert "Ready" in str(rendered.renderable.renderables[2])


def test_render_final_text_uses_strong_color_after_idle() -> None:
    app = VoicePasteApp(Config(), transcriber=FakeTranscriber(), clipboard_writer=Mock())
    app.final_text = "確定テキスト"
    app.state = State.IDLE

    rendered = app.render()

    assert str(rendered.renderable.renderables[4]) == "確定テキスト"
    assert rendered.renderable.renderables[4].style == "green"


def test_render_includes_loading_status() -> None:
    app = VoicePasteApp(Config(), transcriber=FakeTranscriber(), clipboard_writer=Mock())
    app.state = State.LOADING

    rendered = app.render()

    assert "Loading model" in str(rendered.renderable.renderables[2])


def test_run_suppresses_backend_output_during_load(capsys: object) -> None:
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    class NoisyTranscriber(FakeTranscriber):
        def __init__(self) -> None:
            super().__init__()
            self.load = Mock(side_effect=lambda: print("download progress"))

    app = VoicePasteApp(Config(), transcriber=NoisyTranscriber(), clipboard_writer=Mock())

    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        app.load()
    captured = capsys.readouterr()

    assert captured.out == ""


def test_load_preloads_transcriber_and_formatter() -> None:
    transcriber = FakeTranscriber()
    formatter = FakeFormatter()
    app = VoicePasteApp(
        Config(),
        transcriber=transcriber,
        formatter=formatter,
        clipboard_writer=Mock(),
    )

    app.load()

    transcriber.load.assert_called_once()
    formatter.load.assert_called_once()
