# IMPLEMENTATION_PLAN.md — VoicePaste 実装計画

## 実装方針

- 各フェーズは独立して動作確認できる単位で区切る
- フェーズ完了ごとにコミットする
- テストはAGENTS.mdの規約に従う

---

## フェーズ 0 : プロジェクト骨格

**目標** : リポジトリの構造を作り、環境構築が通ることを確認する

### タスク

- [ ] ディレクトリ構成を作成する
- [ ] `requirements-darwin.txt` を作成する
- [ ] `requirements-linux.txt` を作成する
- [ ] `requirements-windows.txt` を作成する
- [ ] `Makefile` を作成する（install / run / test / lint ターゲット）
- [ ] `prepare.bat` を作成する
- [ ] `start.bat` を作成する
- [ ] `config.yaml` のデフォルトを作成する
- [ ] `src/__init__.py` を作成する
- [ ] `tests/__init__.py` を作成する

### 完了条件

```bash
make install  # エラーなく完了する
make lint     # エラーなく完了する
```

---

## フェーズ 1 : config.py

**目標** : config.yaml を読み込み、設定オブジェクトを返す

### タスク

- [ ] `src/config.py` を実装する
- [ ] デフォルト値のフォールバックを実装する
- [ ] `tests/test_config.py` を作成する

### インターフェース

```python
from src.config import load_config

config = load_config("config.yaml")
config.hotkey          # "<cmd>+<shift>+space"
config.model           # "base"
config.language        # "ja"
config.chunk_seconds   # 3
config.formatter.remove_fillers  # True
```

### 完了条件

```bash
make test  # test_config.py がパスする
```

---

## フェーズ 2 : clipboard.py

**目標** : OSを判定してクリップボードにテキストを書き込む

### タスク

- [ ] `src/clipboard.py` を実装する
- [ ] macOS / Linux / Windows を `platform.system()` で分岐する
- [ ] `tests/test_clipboard.py` を作成する（モック使用）

### インターフェース

```python
from src.clipboard import copy_to_clipboard

copy_to_clipboard("こんにちは")  # クリップボードに書き込む
```

### 完了条件

```bash
make test  # test_clipboard.py がパスする
python -c "from src.clipboard import copy_to_clipboard; copy_to_clipboard('test')"
# OS のクリップボードに 'test' が入っている
```

---

## フェーズ 3 : formatter.py

**目標** : `PostFormatter` 抽象インターフェースと `RuleFormatter` を実装する。`LLMFormatter` はローカルGemma 4 E2Bで確定Whisper結果を整形する。

### タスク

- [ ] `src/formatter.py` を実装する（`PostFormatter` 抽象基底クラス・ファクトリ関数）
- [ ] `src/formatter/backends/rule.py` を実装する（`RuleFormatter`）
- [ ] `src/formatter/backends/llm.py` を作成する（macOSはMLX、その他はGGUF）
- [ ] フィラーリストを config から受け取る
- [ ] 正規表現でフィラーを除去する
- [ ] 文末句読点を補完する
- [ ] `tests/test_formatter.py` を作成する

### インターフェース

```python
from src.formatter import PostFormatter
from src.config import load_config

config = load_config("config.yaml")

# ファクトリ経由でバックエンドを切り替える
fmt = PostFormatter.from_config(config.formatter)

fmt.format("えっとこれはテストです")   # → "これはテストです。"
fmt.format("あーなんか良い感じですね") # → "良い感じですね。"
```

### LLMFormatter

```python
class LLMFormatter(PostFormatter):
    def format(self, text: str) -> str:
        ...
```

macOSでは `mlx-vlm` と `mlx-community/gemma-4-e2b-it-4bit` を使用する。
Linux / Windowsでは `llama-cpp-python` と `mradermacher/gemma-4-E2B-it-GGUF` の
`Q4_K_M` を使用する。外部依存はテストで必ずモックする。
システムプロンプトは `formatter.llm.prompt` に直接記述する。
LLM応答は `formatted_text` のみを持つJSONオブジェクトに限定し、自由文応答は受け入れない。

### 完了条件

```bash
make test  # test_formatter.py がパスする
# backend: "rule" → RuleFormatter が動作する
# backend: "llm"  → ローカルLLMで確定テキストが整形される
```

---

## フェーズ 4 : recorder.py

**目標** : sounddevice でマイク入力を録音し、デュアルバッファで2系統に分岐して返す

### タスク

- [ ] `src/recorder.py` を実装する
- [ ] 開始・停止をメソッドで制御できる
- [ ] sounddevice callback 内でデュアルバッファに同時書き込みする
- [ ] `chunk_queue` : chunk_seconds ごとにチャンクを積む（チャンク処理スレッド用）
- [ ] `full_buffer` : 全フレームを蓄積し、停止時にnumpy配列で返す（全体処理用）
- [ ] `tests/test_recorder.py` を作成する（モック使用）

### インターフェース

```python
from src.recorder import Recorder
import queue

chunk_queue = queue.Queue()
rec = Recorder(sample_rate=16000, chunk_seconds=3, chunk_queue=chunk_queue)
rec.start()
# ... 録音中 ...
# chunk_queue には 3 秒ごとに numpy array が積まれる
full_audio = rec.stop()  # 全体の numpy array (float32)
```

### 完了条件

```bash
make test  # test_recorder.py がパスする
python -c "
import queue, time
from src.recorder import Recorder
q = queue.Queue()
rec = Recorder(chunk_seconds=3, chunk_queue=q)
rec.start()
time.sleep(7)
full = rec.stop()
print('chunks:', q.qsize())   # 2チャンク程度
print('full:', full.shape)    # (112000,) 程度
"
```

---

## フェーズ 5 : transcriber.py

**目標** : プラットフォームに応じてWhisperバックエンドを切り替え、全体処理・チャンク処理の両方に対応する

### タスク

- [ ] `src/transcriber.py` を実装する（抽象基底クラス）
- [ ] `src/backends/faster.py` を実装する
- [ ] `src/backends/mlx.py` を実装する（macOS Apple Silicon のみ）
- [ ] プラットフォームとデバイス設定で自動選択する
- [ ] `transcribe(audio)` : 全体処理用・整形なし生テキストを返す
- [ ] `transcribe_chunk(audio)` : チャンク処理用・フィラー除去なし・速度優先
- [ ] `tests/test_transcriber.py` を作成する（モック使用）

### インターフェース

```python
from src.transcriber import Transcriber
from src.config import load_config

config = load_config("config.yaml")
t = Transcriber(config)
t.load()  # モデルをメモリにロード（起動時に一度だけ）

# 全体処理用（録音終了後）
text = t.transcribe(full_audio)        # → "えっとこれはテストです。"

# チャンク処理用（録音中・暫定表示）
text = t.transcribe_chunk(chunk_audio) # → "えっとこれは"
```

### 完了条件

```bash
make test  # test_transcriber.py がパスする
# 実音声で transcribe / transcribe_chunk の両方が返ってくる
```

---

## フェーズ 6 : hotkey.py

**目標** : グローバルホットキーの押下・離上でコールバックを発火する

### タスク

- [ ] `src/hotkey.py` を実装する
- [ ] pynput を使用する
- [ ] ホットキー文字列を config から受け取る
- [ ] `on_press` / `on_release` コールバックを受け取る
- [ ] `tests/test_hotkey.py` を作成する（モック使用）

### インターフェース

```python
from src.hotkey import HotkeyListener

def on_press():
    print("録音開始")

def on_release():
    print("録音停止")

listener = HotkeyListener("<cmd>+<shift>+space", on_press, on_release)
listener.start()
```

### 完了条件

```bash
make test  # test_hotkey.py がパスする
# ホットキー押下でコールバックが発火する
```

---

## フェーズ 7 : main.py (統合・TUI)

**目標** : 全モジュールを統合し、デュアルバッファ処理とRich TUIで動作する

### タスク

- [ ] `src/main.py` を実装する
- [ ] 状態機械（IDLE / RECORDING / PROCESSING / DONE / ERROR）を実装する
- [ ] チャンク処理スレッドを実装する（chunk_queue を消費して暫定表示）
- [ ] 全体処理スレッドを実装する（録音終了後に起動）
- [ ] Rich の `Live` で状態をリアルタイム表示する
- [ ] 暫定テキスト（dim・italic）と確定テキスト（通常）を切り替える
- [ ] 全モジュールを接続する
- [ ] `tests/test_main.py` を作成する（統合テスト、モック使用）

### 状態遷移実装

```python
from enum import Enum, auto

class State(Enum):
    IDLE = auto()
    RECORDING = auto()   # チャンク処理スレッドが並走
    PROCESSING = auto()  # 全体処理スレッドが動作中
    DONE = auto()
    ERROR = auto()
```

### スレッド管理

```python
# 録音開始時
chunk_thread = threading.Thread(target=chunk_worker, daemon=True)
chunk_thread.start()

# 録音終了時
rec.stop() → full_audio
final_thread = threading.Thread(target=final_worker, args=(full_audio,))
final_thread.start()
```

### 完了条件

```bash
make run
# TUIが起動する
# ホットキー押下中：録音中表示＋暫定テキストがリアルタイム更新される
# ホットキーを離す：全体処理後に確定テキストが表示されクリップボードに入る
```

---

## フェーズ 8 : ドキュメント・パッケージング

**目標** : OSSとして公開できる状態にする

### タスク

- [ ] README.md を完成させる
- [ ] CONTRIBUTING.md を作成する
- [ ] LICENSE を選定する（MIT推奨）
- [ ] `pyproject.toml` を作成する
- [ ] GitHub Actions で lint / test を CI する
- [ ] `.github/workflows/ci.yml` を作成する

### CI構成

```yaml
# macOS / Linux / Windows の3環境でテストを走らせる
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    python-version: ["3.11", "3.12"]
```

---

## 依存ライブラリ一覧

### 共通

```
sounddevice
numpy
pynput
rich
pyyaml
```

### macOS Apple Silicon のみ

```
mlx-whisper
```

### macOS Intel / Linux / Windows

```
faster-whisper
```

### 開発用

```
pytest
pytest-cov
ruff
```
