# VoicePaste

Transcribe speech to text using local Whisper and send it straight to your clipboard.  
No subscription. No cloud. Your data never leaves your machine.

[日本語版 README](README.jp.md)

---

## Features

- **Fully local** — audio and text are never sent to an external server
- **Cross-platform** — macOS / Linux / Windows
- **Push-to-Talk** — records only while the hotkey is held
- **Fast** — uses mlx-whisper on Apple Silicon, faster-whisper everywhere else
- **TUI or GUI** — real-time status display in the terminal or a floating window
- **Simple** — copies to clipboard; you decide when to paste
- **LLM polish** — optionally refines the final Whisper output with a local Gemma 4 E2B model

---

## How it works

```
Hold hotkey  → Recording...
Release      → Transcribing...
             → ✓ Copied to clipboard
Paste anywhere (Cmd+V / Ctrl+V / C-y)
```

---

## Installation

### macOS / Linux

```bash
git clone https://github.com/yourname/voicepaste
cd voicepaste
make install
```

### Windows

```bat
git clone https://github.com/yourname/voicepaste
cd voicepaste
prepare.bat
```

> **LLM model download**  
> `make install` / `prepare.bat` installs dependencies and then automatically downloads the LLM model if `formatter.backend` is set to `"llm"` in `config.yaml` (first run only — may take a few minutes). If set to `"rule"` the download is skipped.

### Linux note

xclip is required:

```bash
# Ubuntu / Debian
sudo apt install xclip

# Arch
sudo pacman -S xclip
```

---

## Running

### macOS / Linux

```bash
make run
```

To use the always-on-top GUI:

```bash
make run-gui
```

### Windows

```bat
start.bat
```

To use the always-on-top GUI:

```bat
python -m src.gui
```

The GUI uses Python's standard Tkinter toolkit, so VoicePaste does not need an
extra GUI dependency. The window is kept above other windows on macOS, Windows,
and Linux while it shows the same Ready / RECORDING / PROCESSING / Done / Error
states as the TUI. On macOS, the GUI window opens after model loading to avoid a
native Tk / MLX runtime crash; loading progress is printed in the terminal first.

---

## Permissions

On first launch the OS will request:

| Permission | Reason |
|------------|--------|
| Microphone | Audio recording |
| Accessibility | Global hotkey listener |

These permissions are used locally only.

---

## Configuration

Edit `config.yaml` to customise behaviour:

```yaml
hotkey: "<cmd>+<shift>+space"   # global hotkey
model: "base"                    # tiny / base / small / medium / large
language: "ja"                   # transcription language
device: "auto"                   # auto / cpu / cuda / mlx
chunk_seconds: 3                 # interim-display chunk length in seconds
formatter:
  backend: "rule"                # rule / llm
  remove_fillers: true           # strip filler words
  add_punctuation: true          # add punctuation
  fillers:
    - "あー"
    - "えっと"
    - "なんか"
    - "えー"
    - "あの"
    - "まあ"
    - "ちょっと待って"
  llm:
    prompt: |
      You are an editor that polishes voice-input transcripts.
      Clean up the Whisper output into natural, readable text without changing the meaning.
      Remove fillers, false starts, and extra whitespace; add punctuation where needed.
      Do not guess at proper nouns, numbers, code, or URLs.
    backend: "auto"              # auto / mlx / gguf
    mlx_model: "mlx-community/gemma-4-e2b-it-4bit"
    gguf_repo_id: "mradermacher/gemma-4-E2B-it-GGUF"
    gguf_filename: "*Q4_K_M.gguf"
    models_dir: "models"
    max_tokens: 256
    temperature: 0.0
    n_ctx: 4096
    n_gpu_layers: -1
```

### LLM formatting

Set `formatter.backend: "llm"` to refine the final Whisper output with a local LLM.
Interim (mid-recording) previews are not LLM-processed for speed.
The system prompt is configured directly in `formatter.llm.prompt`.

On macOS the MLX model `mlx-community/gemma-4-e2b-it-4bit` is used.
On Linux / Windows `llama-cpp-python` loads the GGUF model `mradermacher/gemma-4-E2B-it-GGUF` (`Q4_K_M`).

Models are downloaded automatically by `make install` / `prepare.bat` and stored in `models/`
at the project root. The contents of `models/` are excluded by `.gitignore`.
For fully offline use, download the model in advance and set `model` to a local path or model ID.

### Whisper model sizes

| Model | Accuracy | Speed | Memory |
|-------|----------|-------|--------|
| tiny | low | fastest | ~150 MB |
| base | medium | fast | ~300 MB |
| small | high | moderate | ~500 MB |
| medium | best | slow | ~1.5 GB |

For Japanese, `small` or larger is recommended.

On Apple Silicon with `device: "auto"` or `device: "mlx"`, model names are automatically
mapped to their MLX equivalents — e.g. `base` → `mlx-community/whisper-base-mlx`.

Audio and transcription results are never sent to external servers. On first run, Whisper
model weights will be downloaded if not already cached locally.

---

## Development

```bash
make install   # install dependencies (+ LLM model if configured)
make test      # run tests
make lint      # run linter
make run       # start the app
make run-gui   # start the floating GUI
```

To launch directly: `python -m src.main` or `python -m src.gui`.

### Debugging microphone input

The recording is saved to `debug/last_recording.wav` just before being passed to Whisper.
If that WAV is silent, check that the application running VoicePaste
(Terminal / iTerm / etc.) has microphone permission in
**System Settings → Privacy & Security → Microphone**.

Run a short mic check:

```bash
make mic-test
```

The test audio is saved to `debug/mic_check.wav`.

To fix a specific input device, set `input_device` in `config.yaml` to the ID shown by `make mic-test`:

```yaml
input_device: 1
```

Please read `AGENTS.md` and `CONTRIBUTING.md` before contributing.

---

## License

MIT
