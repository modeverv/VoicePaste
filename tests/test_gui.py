from __future__ import annotations

from unittest.mock import Mock

from src.config import Config
from src.gui import GuiViewModel, VoicePasteGui
from src.main import State, VoicePasteApp
from src.mic_level import MicLevel


class FakeTranscriber:
    def load(self) -> None:
        """Test double: no model needs to be loaded for GUI view-model tests."""


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

    def bind(self, sequence: str, callback: object) -> None:
        self.calls.append(("bind", (sequence, callback)))

    def withdraw(self) -> None:
        self.calls.append(("withdraw", ()))

    def deiconify(self) -> None:
        self.calls.append(("deiconify", ()))

    def lift(self) -> None:
        self.calls.append(("lift", ()))

    def focus_force(self) -> None:
        self.calls.append(("focus_force", ()))

    def after(self, delay_ms: int, callback: object) -> None:
        self.calls.append(("after", (delay_ms, callback)))
        if callable(callback):
            callback()

    def destroy(self) -> None:
        self.calls.append(("destroy", ()))


class FakeLevelMonitor:
    def __init__(self) -> None:
        self.is_running = False
        self.start = Mock(side_effect=self._start)
        self.stop = Mock(side_effect=self._stop)

    def _start(self) -> None:
        self.is_running = True

    def _stop(self) -> None:
        self.is_running = False


class FakeCanvas:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def winfo_width(self) -> int:
        return 100

    def winfo_height(self) -> int:
        return 20

    def delete(self, *args: object) -> None:
        self.calls.append(("delete", args, {}))

    def create_rectangle(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("create_rectangle", args, kwargs))

    def create_line(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("create_line", args, kwargs))

    def create_text(self, *args: object, **kwargs: object) -> None:
        self.calls.append(("create_text", args, kwargs))


class FakeLabel:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.kwargs.update(kwargs)


def test_gui_configures_always_on_top_window() -> None:
    root = FakeRoot()
    gui = VoicePasteGui(make_app(), root=root)

    gui._configure_root()

    assert ("title", ("VoicePaste",)) in root.calls
    assert ("attributes", ("-topmost", True)) in root.calls
    assert any(call[0] == "protocol" and call[1][0] == "WM_DELETE_WINDOW" for call in root.calls)
    assert any(call[0] == "bind" and call[1][0] == "<Escape>" for call in root.calls)
    assert ("withdraw", ()) not in root.calls


def test_gui_close_stops_listener_and_destroys_window() -> None:
    root = FakeRoot()
    listener = Mock()
    gui = VoicePasteGui(make_app(), root=root)
    gui.listener = listener

    gui.close()

    listener.stop.assert_called_once()
    assert ("destroy", ()) in root.calls


def test_gui_hotkey_callbacks_pause_idle_level_monitor() -> None:
    root = FakeRoot()
    app = make_app()
    app.start_recording = Mock()
    app.stop_recording = Mock()
    monitor = FakeLevelMonitor()
    gui = VoicePasteGui(app, root=root)
    gui._level_monitor = monitor

    gui._start_recording()
    gui._stop_recording()

    monitor.stop.assert_called_once()
    app.start_recording.assert_called_once()
    app.stop_recording.assert_called_once()
    monitor.start.assert_called_once()


def test_gui_hotkey_press_shows_window_and_starts_recording() -> None:
    root = FakeRoot()
    app = make_app()
    app.start_recording = Mock()
    monitor = FakeLevelMonitor()
    gui = VoicePasteGui(app, root=root)
    gui._level_monitor = monitor

    gui._on_hotkey_press()

    assert ("deiconify", ()) in root.calls
    assert ("lift", ()) in root.calls
    assert ("attributes", ("-topmost", True)) in root.calls
    assert ("focus_force", ()) in root.calls
    app.start_recording.assert_called_once()


def test_gui_escape_stops_recording_and_hides_window() -> None:
    root = FakeRoot()
    app = make_app()
    app.stop_recording = Mock()
    monitor = FakeLevelMonitor()
    gui = VoicePasteGui(app, root=root)
    gui._level_monitor = monitor

    gui._hide_window()

    app.stop_recording.assert_called_once()
    assert ("withdraw", ()) in root.calls


def test_gui_renders_bar_style_level_meter() -> None:
    gui = VoicePasteGui(make_app(), root=FakeRoot())
    canvas = FakeCanvas()
    value_label = FakeLabel()
    gui._level_canvas = canvas
    gui._level_value_label = value_label

    gui._render_level_meter(MicLevel(rms=0.01, peak=0.1))

    assert ("delete", ("all",), {}) in canvas.calls
    rectangles = [call for call in canvas.calls if call[0] == "create_rectangle"]
    lines = [call for call in canvas.calls if call[0] == "create_line"]
    texts = [call for call in canvas.calls if call[0] == "create_text"]
    assert rectangles[-1][1] == (0, 2, 33, 18)
    assert lines[-1][1] == (66, 0, 66, 20)
    assert texts[-1][1] == (82, 10.0)
    assert texts[-1][2]["anchor"] == "w"
    assert value_label.kwargs["text"] == "RMS -40.0  Peak -20.0 dBFS"
