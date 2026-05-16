"""Small microphone diagnostic command."""

from __future__ import annotations

import os
import queue
import sys
import time

import numpy as np

from src.audio_debug import audio_rms, save_wav
from src.config import load_config


def main() -> None:
    """Record a short sample and print microphone level diagnostics."""

    import sounddevice as sd

    config = load_config("config.yaml")
    device = _device_from_env(config.input_device)
    info = sd.query_devices(device, "input")
    input_rate = (
        int(info["default_samplerate"])
        if config.input_sample_rate == "auto"
        else int(config.input_sample_rate)
    )
    seconds = int(os.environ.get("SECONDS", "8"))
    print("Input devices:")
    for index, candidate in enumerate(sd.query_devices()):
        if candidate["max_input_channels"] > 0:
            marker = "*" if candidate["name"] == info["name"] else " "
            print(
                f" {marker} {index}: {candidate['name']} "
                f"({candidate['max_input_channels']} ch, {candidate['default_samplerate']} Hz)"
            )
    print()
    print(f"Using input device: {info['name']} ({input_rate} Hz)")
    print(f"Recording {seconds} seconds. Speak now and watch the live peak meter...")
    mono = _record_with_meter(sd, device, input_rate, seconds)
    rms = audio_rms(mono)
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    save_wav(mono, "debug/mic_check.wav", input_rate)
    print(f"RMS: {rms:.8f}")
    print(f"Peak: {peak:.8f}")
    print("Saved: debug/mic_check.wav")
    if rms < 1e-5:
        print("Result: silent. Check macOS Microphone permission for this app/terminal.")
    else:
        print("Result: microphone input detected.")
    time.sleep(0.1)


def _device_from_env(default: object) -> object:
    raw = os.environ.get("DEVICE")
    if raw is None:
        return default
    text = raw.strip()
    if text.isdigit():
        return int(text)
    return text


def _record_with_meter(
    sounddevice: object,
    device: object,
    input_rate: int,
    seconds: int,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    levels: queue.Queue[tuple[float, float]] = queue.Queue()

    def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        del frames, time_info
        if status:
            print(f"\nInput status: {status}", file=sys.stderr)
        mono = indata.reshape(-1).astype(np.float32).copy()
        chunks.append(mono)
        levels.put((audio_rms(mono), float(np.max(np.abs(mono))) if mono.size else 0.0))

    with sounddevice.InputStream(
        samplerate=input_rate,
        device=device,
        channels=1,
        dtype="float32",
        callback=callback,
    ):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                rms, peak = levels.get(timeout=0.2)
            except queue.Empty:
                rms, peak = 0.0, 0.0
            bar = "#" * min(40, int(peak * 400))
            print(f"\rRMS {rms:.8f}  Peak {peak:.8f}  {bar:<40}", end="", flush=True)
    print()
    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32, copy=False)


if __name__ == "__main__":
    main()
