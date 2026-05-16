# VoicePaste

ローカルWhisperで音声をテキストに変換し、クリップボードに送る。  
AquaVoice要らず。サブスク不要。データはあなたのマシンから出ない。

---

## 特徴

- **完全ローカル** : 音声・テキストが外部サーバーに送信されない
- **クロスプラットフォーム** : macOS / Linux / Windows 対応
- **Push-to-Talk** : ホットキーを押している間だけ録音する
- **高速** : macOS Apple Silicon では mlx-whisper、その他は faster-whisper を使用
- **TUI** : ターミナルにリアルタイムで状態を表示する
- **シンプル** : クリップボードに入れるだけ。ペーストのタイミングは自分で決める
- **LLM整形** : 確定Whisper結果をローカルGemma 4 E2Bで自然な文章へ整形できる

---

## 動作イメージ

```
ホットキーを押す → 録音中...
ホットキーを離す → 文字起こし中...
                 → ✓ クリップボードにコピーされました
好きな場所でペースト（Cmd+V / Ctrl+V / C-y）
```

---

## インストール

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

### Linux の注意事項

xclip が必要です。

```bash
# Ubuntu / Debian
sudo apt install xclip

# Arch
sudo pacman -S xclip
```

---

## 起動

### macOS / Linux

```bash
make run
```

### Windows

```bat
start.bat
```

---

## 権限について

初回起動時にOSから以下の権限を求められます。

| 権限 | 理由 |
|------|------|
| マイク | 音声録音のため |
| アクセシビリティ | グローバルホットキーのため |

これらの権限はローカルでのみ使用されます。

---

## 設定

`config.yaml` を編集して設定を変更できます。

```yaml
hotkey: "<cmd>+<shift>+space"   # グローバルホットキー
model: "base"                    # tiny / base / small / medium / large
language: "ja"                   # 文字起こし言語
device: "auto"                   # auto / cpu / cuda / mlx
chunk_seconds: 3                 # 暫定表示のチャンク秒数
formatter:
  backend: "rule"                # rule / llm
  remove_fillers: true           # あー・えっと等を除去する
  add_punctuation: true          # 句読点を補完する
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

### LLM整形

`formatter.backend: "llm"` にすると、録音終了後の確定Whisper結果だけをローカルLLMで整形します。
録音中の暫定表示は速度優先のためLLM整形しません。
LLM応答は `{"formatted_text": "..."}` のJSONオブジェクトに限定し、余分なキーや自由文はエラーとして扱います。
システムプロンプトは `formatter.llm.prompt` に直接記述します。

macOSではMLX版の `mlx-community/gemma-4-e2b-it-4bit` を使用します。Linux / Windowsでは
`llama-cpp-python` からGGUF版の `mradermacher/gemma-4-E2B-it-GGUF` の `Q4_K_M` を使用します。
初回実行時はHugging Faceからモデルのダウンロードが発生します。完全オフラインで使う場合は
事前にモデルを取得し、`model` にローカルの `.gguf` ファイルパス、または利用したいモデルIDを指定してください。
LLMモデルは `models_dir` 配下に保存され、既定ではプロジェクト直下の `models/` に入ります。
`models/` の中身は `.gitignore` で除外されます。

### モデルサイズの目安

| モデル | 精度 | 速度 | メモリ |
|--------|------|------|--------|
| tiny | 低 | 最速 | ~150MB |
| base | 中 | 速い | ~300MB |
| small | 高 | 普通 | ~500MB |
| medium | 最高 | 遅い | ~1.5GB |

日本語の場合、`small` 以上を推奨します。

Apple Silicon で `device: "auto"` または `device: "mlx"` の場合、`tiny` / `base` /
`small` / `medium` / `large` は MLX 用モデルに自動変換されます。たとえば `base` は
`mlx-community/whisper-base-mlx` として扱われます。

音声データと文字起こし結果は外部サーバーに送信しません。ただし、モデルがローカルに
キャッシュされていない初回起動時は、Whisper モデルのダウンロードが発生する場合があります。
完全オフラインで使う場合は事前にモデルを取得し、`model` にローカルモデルディレクトリのパスを指定してください。

---

## 開発

```bash
make install   # 依存関係のインストール
make test      # テストの実行
make lint      # リントの実行
make run       # 起動
```

Python から直接起動する場合は `python -m src.main` を使用します。

### マイク入力のデバッグ

録音結果は Whisper に渡す直前に `debug/last_recording.wav` へ保存されます。
この WAV が無音の場合、まず macOS の `システム設定 > プライバシーとセキュリティ > マイク` で、
VoicePaste を起動しているアプリ（Terminal / iTerm / PyCharm / Codex など）にマイク権限があるか確認してください。

短いマイク診断は次で実行できます。

```bash
make mic-test
```

診断音声は `debug/mic_check.wav` に保存されます。

入力デバイスを固定したい場合は、`make mic-test` に表示される番号を `config.yaml` の
`input_device` に指定します。

```yaml
input_device: 1  # 例: MacBook Proのマイク
```

コントリビュートの前に `AGENTS.md` と `CONTRIBUTING.md` を読んでください。

---

## ライセンス

MIT
