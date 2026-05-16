from __future__ import annotations

import queue
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
    def format(self, text: str) -> str:
        return text.replace("えっと", "") + "。"


def test_app_recording_to_clipboard_flow() -> None:
    recorder_holder: dict[str, FakeRecorder] = {}

    def recorder_factory(chunk_queue: queue.Queue[AudioArray | None]) -> FakeRecorder:
        recorder = FakeRecorder(chunk_queue)
        recorder_holder["recorder"] = recorder
        return recorder

    clipboard = Mock()
    app = VoicePasteApp(
        Config(),
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


def test_app_sets_error_when_final_processing_fails() -> None:
    transcriber = FakeTranscriber()
    transcriber.transcribe.side_effect = RuntimeError("boom")
    app = VoicePasteApp(Config(), transcriber=transcriber, clipboard_writer=Mock())

    app._final_worker(np.ones(4, dtype=np.float32))

    assert app.state == State.ERROR
    assert app.error_text == "boom"


def test_render_includes_ready_status() -> None:
    app = VoicePasteApp(Config(), transcriber=FakeTranscriber(), clipboard_writer=Mock())

    rendered = app.render()

    assert "Ready" in str(rendered.renderable.renderables[2])
