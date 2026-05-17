from __future__ import annotations

from unittest.mock import Mock

from src.config import Config
from src.gui import GuiViewModel, VoicePasteGui
from src.main import State, VoicePasteApp


class FakeTranscriber:
    def load(self) -> None:
        pass


def make_app() -> VoicePasteApp:
    return VoicePasteApp(Config(), transcriber=FakeTranscriber(), clipboard_writer=Mock())


def test_view_model_maps_recording_preview() -> None:
    app = make_app()
    app.state = State.RECORDING
    app.preview_text = "途中テキスト"

    vm = GuiViewModel.from_app(app)

    assert vm.status == "● RECORDING..."
    assert vm.body == "途中テキスト"
    assert vm.body_italic is True


def test_view_model_maps_done_final_text() -> None:
    app = make_app()
    app.state = State.DONE
    app.final_text = "確定テキスト"

    vm = GuiViewModel.from_app(app)

    assert vm.status == "✓ Copied to clipboard"
    assert vm.body == "確定テキスト"
    assert vm.body_italic is False


def test_view_model_maps_error_text() -> None:
    app = make_app()
    app.state = State.ERROR
    app.error_text = "boom"

    vm = GuiViewModel.from_app(app)

    assert vm.status == "✗ ERROR"
    assert vm.body == "boom"
    assert vm.body_color == "#e53e3e"


class FakeRoot:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def title(self, value: str) -> None:
        self.calls.append(("title", (value,)))

    def geometry(self, value: str) -> None:
        self.calls.append(("geometry", (value,)))

    def resizable(self, width: bool, height: bool) -> None:
        self.calls.append(("resizable", (width, height)))

    def attributes(self, name: str, value: bool) -> None:
        self.calls.append(("attributes", (name, value)))

    def protocol(self, name: str, callback: object) -> None:
        self.calls.append(("protocol", (name, callback)))

    def destroy(self) -> None:
        self.calls.append(("destroy", ()))


def test_gui_configures_always_on_top_window() -> None:
    root = FakeRoot()
    gui = VoicePasteGui(make_app(), root=root)

    gui._configure_root()

    assert ("title", ("VoicePaste",)) in root.calls
    assert ("attributes", ("-topmost", True)) in root.calls
    assert any(call[0] == "protocol" and call[1][0] == "WM_DELETE_WINDOW" for call in root.calls)


def test_gui_close_stops_listener_and_destroys_window() -> None:
    root = FakeRoot()
    listener = Mock()
    gui = VoicePasteGui(make_app(), root=root)
    gui.listener = listener

    gui.close()

    listener.stop.assert_called_once()
    assert ("destroy", ()) in root.calls
