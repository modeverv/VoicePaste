from __future__ import annotations

from rich.console import Console

from src.config import Config
from src.microphone import list_input_devices, select_microphone


def fake_query_devices(device: object = None, kind: object = None) -> object:
    if device is None and kind == "input":
        return {"name": "Built-in Mic", "default_samplerate": 48000.0}
    return [
        {"name": "Built-in Mic", "max_input_channels": 1, "default_samplerate": 48000.0},
        {"name": "Speaker", "max_input_channels": 0, "default_samplerate": 48000.0},
        {"name": "USB Mic", "max_input_channels": 2, "default_samplerate": 44100.0},
    ]


def test_list_input_devices_filters_outputs_and_marks_default() -> None:
    devices = list_input_devices(fake_query_devices)

    assert [device.index for device in devices] == [0, 2]
    assert devices[0].name == "Built-in Mic"
    assert devices[0].is_default is True
    assert devices[1].name == "USB Mic"
    assert devices[1].is_default is False


def test_select_microphone_returns_config_with_selected_device() -> None:
    console = Console(record=True)

    config = select_microphone(
        Config(input_device=None),
        console=console,
        prompt=lambda *args, **kwargs: "2",
        query_devices=fake_query_devices,
    )

    assert config.input_device == 2
    assert "USB Mic" in console.export_text()


def test_select_microphone_keeps_configured_device_on_default_choice() -> None:
    config = select_microphone(
        Config(input_device="Built-in Mic"),
        console=Console(record=True),
        prompt=lambda *args, **kwargs: "d",
        query_devices=fake_query_devices,
    )

    assert config.input_device == "Built-in Mic"
