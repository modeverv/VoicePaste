"""Startup microphone selection UI."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from src.config import Config, InputDevice


@dataclass(frozen=True)
class MicrophoneDevice:
    """A selectable input device."""

    index: int
    name: str
    channels: int
    default_samplerate: int
    is_default: bool = False


def select_microphone(
    config: Config,
    console: Console | None = None,
    prompt: Callable[..., str] = Prompt.ask,
    query_devices: Callable[..., Any] | None = None,
) -> Config:
    """Ask the user which input device to use for this session.

    Args:
        config: Current application configuration.
        console: Optional Rich console for rendering the selection UI.
        prompt: Prompt function, injectable for tests.
        query_devices: Optional sounddevice query function.

    Returns:
        A config copy with the selected input device for this process.
    """

    console = console or Console()
    try:
        devices = list_input_devices(query_devices)
    except Exception as exc:  # pragma: no cover - defensive startup path
        console.print(f"[yellow]Could not list microphones: {exc}[/yellow]")
        return config
    if not devices:
        console.print("[yellow]No input microphones were found. Using system default.[/yellow]")
        return config

    _render_microphone_table(console, devices, config.input_device)
    choices = ["d", *(str(device.index) for device in devices)]
    answer = prompt(
        "select input device",
        choices=choices,
        default="d",
        show_choices=False,
    )
    selected = _selected_device(answer, devices, config.input_device)
    return cast(Config, replace(config, input_device=selected))


def list_input_devices(query_devices: Callable[..., Any] | None = None) -> list[MicrophoneDevice]:
    """Return available audio input devices."""

    if query_devices is None:
        import sounddevice as sd

        query_devices = sd.query_devices

    all_devices = query_devices()
    default_info = query_devices(None, "input")
    default_name = str(default_info.get("name", ""))
    devices: list[MicrophoneDevice] = []
    for index, raw in enumerate(all_devices):
        channels = int(raw.get("max_input_channels", 0))
        if channels <= 0:
            continue
        devices.append(
            MicrophoneDevice(
                index=index,
                name=str(raw.get("name", f"Input {index}")),
                channels=channels,
                default_samplerate=int(raw.get("default_samplerate", 0)),
                is_default=str(raw.get("name", "")) == default_name,
            )
        )
    return devices


def _render_microphone_table(
    console: Console,
    devices: Sequence[MicrophoneDevice],
    configured_device: InputDevice,
) -> None:
    table = Table(title="Microphone")
    table.add_column("ID", justify="right")
    table.add_column("Name")
    table.add_column("Ch", justify="right")
    table.add_column("Hz", justify="right")
    table.add_column("Default")
    for device in devices:
        configured = _matches_configured_device(device, configured_device)
        if configured:
            marker = "config"
        elif device.is_default:
            marker = "system"
        else:
            marker = ""
        table.add_row(
            str(device.index),
            device.name,
            str(device.channels),
            str(device.default_samplerate),
            marker,
        )
    body = Text("press enter then use default mic。input number then use selected mic.")
    console.print(Panel.fit(table, title="VoicePaste"))
    console.print(body)


def _selected_device(
    answer: str,
    devices: Sequence[MicrophoneDevice],
    configured_device: InputDevice,
) -> InputDevice:
    text = answer.strip().lower()
    if text in {"", "d"}:
        return configured_device
    selected_index = int(text)
    for device in devices:
        if device.index == selected_index:
            return device.index
    return configured_device


def _matches_configured_device(device: MicrophoneDevice, configured_device: InputDevice) -> bool:
    return configured_device == device.index or configured_device == device.name
