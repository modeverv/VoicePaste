# SPEC.md — VoicePaste 仕様書

## 概要

VoicePaste は、音声入力をローカルWhisperで文字起こしし、クリップボードに貼り付けるクロスプラットフォームのCLIツールである。AquaVoice等の有料SaaSに依存せず、完全ローカル・無料で同等の体験を提供することを目的とする。

---

## 設計原則

- **ローカルファースト** : 音声・テキストデータが外部サーバーに送信されない
- **クロスプラットフォーム** : macOS / Linux / Windows で同一コードベースで動作する
- **最小権限** : マイク権限 + アクセシビリティ権限（ホットキー用）のみ要求する
- **依存最小** : 外部バイナリへの依存を避け、Pythonライブラリで完結させる
- **自己完結** : BTT / Automator 等の外部ツールに依存しない

---

## 機能要件

### コア機能

| ID | 機能 | 説明 |
|----|------|------|
| F-01 | 音声録音 | グローバルホットキー押下中に録音する（Push-to-Talk方式） |
| F-02 | 文字起こし | ローカルWhisperモデルで文字起こしする |
| F-03 | テキスト整形 | ルールベース、またはローカルLLMでフィラー除去・句読点補完を行う |
| F-04 | クリップボード出力 | 整形済みテキストをOSのクリップボードに書き込む |
| F-05 | TUI表示 | 現在の状態をターミナルにリアルタイム表示する |
| F-06 | グローバルホットキー | アプリのフォーカスに依存しないホットキーで録音開始・停止する |

### 非機能要件

| ID | 要件 | 目標値 |
|----|------|--------|
| N-01 | 文字起こしレイテンシ | 録音終了から2秒以内にクリップボードへ書き込む |
| N-02 | 起動時間 | モデルロード込みで10秒以内 |
| N-03 | メモリ使用量 | 待機時500MB以内（モデルサイズ依存） |
| N-04 | オフライン動作 | インターネット接続なしで全機能が動作する |

---

## 対応プラットフォーム

| OS | Whisperバックエンド | ホットキー | クリップボード |
|----|---------------------|------------|----------------|
| macOS (Apple Silicon) | mlx-whisper | pynput | pbcopy (subprocess) |
| macOS (Intel) | faster-whisper | pynput | pbcopy (subprocess) |
| Linux | faster-whisper | pynput | xclip (subprocess) |
| Windows | faster-whisper | pynput | clip (subprocess) |

---

## アーキテクチャ

```
src/
├── main.py               # エントリーポイント、TUIループ・状態管理
├── recorder.py           # sounddeviceによる録音・デュアルバッファ管理
├── transcriber.py        # Whisperバックエンド抽象化
│   └── backends/
│       ├── mlx.py        # mlx-whisper (macOS Apple Silicon)
│       └── faster.py     # faster-whisper (その他)
├── formatter.py          # Formatterインターフェース定義・ファクトリ関数
│   └── backends/
│       ├── rule.py       # ルールベース整形（デフォルト）
│       └── llm.py        # ローカルLLM整形（Gemma 4 E2B）
├── clipboard.py          # OSクリップボード書き込み
├── hotkey.py             # pynputによるグローバルホットキー
└── config.py             # config.yaml の読み込み
```

### デュアルバッファ構成

録音中の音声データを2系統に分岐して処理する。

```
マイク入力 (sounddevice callback)
    ↓
  tee（分岐）
    ├── chunk_queue  → チャンク処理スレッド
    │                    → Whisper(chunk) → TUI暫定表示（薄色・イタリック）
    │                    ※ chunk_seconds ごとに処理
    └── full_buffer  ← 録音終了まで蓄積
                          ↓（録音終了）
                       全体処理スレッド
                          → Whisper(full)
                          → PostFormatter（抽象インターフェース）
                          │   ├── RuleFormatter（デフォルト）
                          │   └── LLMFormatter（Gemma 4 E2B ローカル整形）
                          → TUI確定表示（通常色）
                          → pbcopy
```

### スレッド構成

| スレッド | 役割 |
|----------|------|
| メインスレッド | TUIループ・状態管理 |
| 録音スレッド | sounddevice callback・デュアルバッファへの書き込み |
| チャンク処理スレッド | chunk_queue を消費してWhisper→暫定表示 |
| 全体処理スレッド | 録音終了後に起動・Whisper全体→整形→pbcopy |

### 状態遷移

```
IDLE（待機中）
  └─[ホットキー押下]→ RECORDING（録音中）
        │                ↑チャンク処理スレッドが並走
        └─[ホットキー離す]→ PROCESSING（処理中）
              ├─[成功]→ DONE（完了）→ IDLE
              └─[失敗]→ ERROR（エラー）→ IDLE
```

---

## 設定ファイル (config.yaml)

```yaml
hotkey: "<cmd>+<shift>+space"   # グローバルホットキー
model: "base"                    # Whisperモデルサイズ (tiny/base/small/medium/large)
language: "ja"                   # 文字起こし言語
device: "auto"                   # auto / cpu / cuda / mla
chunk_seconds: 3                 # リアルタイム表示のチャンク秒数（1〜10推奨）
formatter:
  backend: "rule"                # 整形バックエンド: rule / llm
  remove_fillers: true           # フィラー除去（rule バックエンド時）
  add_punctuation: true          # 句読点補完（rule バックエンド時）
  fillers:                       # 除去対象フィラーリスト（rule バックエンド時）
    - "あー"
    - "えっと"
    - "なんか"
    - "えー"
    - "あの"
    - "まあ"
    - "ちょっと待って"
  llm:                           # llm バックエンド時の設定
    endpoint: "http://localhost:1234/v1"  # LM Studio等のOpenAI互換エンドポイント
    model: "auto"                # 使用するモデル名（autoでエンドポイントのデフォルト）
    prompt: |                    # システムプロンプト
      あなたは音声入力の確定テキストを整形する編集者です。
      Whisperの文字起こし結果を、意味を変えずに読みやすい日本語へ整えてください。
      フィラー、言い直し、余分な空白を削り、必要な句読点を補ってください。
      固有名詞、数値、コード、URLは推測で変更しないでください。
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

---

## TUI仕様

Richライブラリを使用する。フローティングウィンドウではなくターミナル内表示。

### 録音中（チャンク処理結果をリアルタイム表示）

```
┌─────────────────────────────────────┐
│  VoicePaste                         │
│                                     │
│  ● RECORDING...                     │
│                                     │
│  ~ えっとこれは、なんか              │  ← 薄いグレー・イタリック
│    テストの文章で                    │    チャンク結果・随時更新
│                                     │
└─────────────────────────────────────┘
```

### 全体処理完了後（確定表示）

```
┌─────────────────────────────────────┐
│  VoicePaste                         │
│                                     │
│  ✓ Copied to clipboard              │
│                                     │
│  これはテストの文章です。            │  ← 通常色・フィラー除去済み確定テキスト
│                                     │
└─────────────────────────────────────┘
```

### 待機中

```
┌─────────────────────────────────────┐
│  VoicePaste                         │
│                                     │
│  ○ Ready  [Cmd+Shift+Space]         │  ← グレー
│                                     │
│  これはテストの文章です。            │  ← 前回の確定テキスト（薄く残す）
│                                     │
└─────────────────────────────────────┘
```

### 表示仕様まとめ

| 状態 | アイコン | 色 | テキスト表示 |
|------|----------|----|-------------|
| IDLE | ○ | グレー | 前回確定テキスト（dim） |
| RECORDING | ● | 赤 | チャンク暫定テキスト（dim・italic） |
| PROCESSING | ⚙ | 黄 | 最後のチャンク暫定テキスト（dim・italic） |
| DONE | ✓ | 緑 | 確定テキスト（通常） |
| ERROR | ✗ | 赤 | エラーメッセージ |

---

## PostFormatter 仕様

全体処理（録音終了後）のテキスト整形を担う抽象インターフェース。ルールベースとローカルLLMバックエンドを差し替え可能な構造にする。

### インターフェース定義

```python
from abc import ABC, abstractmethod

class PostFormatter(ABC):
    """全体処理テキストの整形インターフェース。"""

    @abstractmethod
    def format(self, text: str) -> str:
        """Whisperの生テキストを整形して返す。"""
        ...

    @classmethod
    def from_config(cls, config: FormatterConfig) -> "PostFormatter":
        """config.formatter.backend に応じてインスタンスを返すファクトリ。"""
        match config.backend:
            case "rule":
                return RuleFormatter(config)
            case "llm":
                return LLMFormatter(config)
            case _:
                raise ValueError(f"Unknown formatter backend: {config.backend}")
```

### 適用タイミング

| 処理 | PostFormatter | 対象 |
|------|--------------|------|
| チャンク処理（暫定表示） | **適用しない** | 生テキストをそのまま表示 |
| 全体処理（確定テキスト） | **適用する** | フィラー除去・整形済みをpbcopy |

チャンク処理中はフィラーをそのまま表示する。「話し途中の生の文字起こし」と「整形済み確定テキスト」の差分がユーザーに自然に伝わる。

### RuleFormatter（デフォルト実装）

```python
class RuleFormatter(PostFormatter):
    """ルールベースの整形。依存ゼロ・即時動作。"""
```

処理内容：

- config.yamlのフィラーリストを正規表現で除去する
- 文頭・文末の余分な空白を除去する
- 連続する句読点を正規化する
- Whisper出力に句読点がない場合、文末に「。」を付与する
- 長文（句点なしで50文字超）は読点「、」を推定位置に補完する（オプション）

### LLMFormatter

```python
class LLMFormatter(PostFormatter):
    """ローカルLLMによる確定Whisperテキスト整形。"""

    def format(self, text: str) -> str:
        ...
```

実装方針：

- macOSは `mlx-vlm` と `mlx-community/gemma-4-e2b-it-4bit` を使用する
- Linux / Windowsは `llama-cpp-python` と `mradermacher/gemma-4-E2B-it-GGUF` の `Q4_K_M` を使用する
- 初回実行時はHugging Faceからモデルを取得し、以後は `models_dir` 配下を使用する
- LLM backendはメインUI表示前の起動ロード時にモデル取得とロードを完了する
- 録音中のチャンク暫定表示には適用せず、確定Whisper結果だけを整形する
- システムプロンプトは `formatter.llm.prompt` に直接記述する
- LLM応答は `{"formatted_text": "..."}` のJSONオブジェクトに限定し、余分なキーや自由文は失敗として扱う
- GGUF backendでは `response_format` にJSON Schemaを渡して生成を制約する

---

## 将来の拡張（スコープ外）

- OpenAI互換サーバー経由の任意ローカルLLM整形
- 文字起こし履歴のログ保存
- GUIフロントエンド
- Whisper以外のSTTバックエンド対応（Vosk等）
