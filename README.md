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
  backend: "rule"                # rule / llm（llmは現時点でstub）
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
    endpoint: "http://localhost:1234/v1"
    model: "auto"
    prompt: ""
```

### モデルサイズの目安

| モデル | 精度 | 速度 | メモリ |
|--------|------|------|--------|
| tiny | 低 | 最速 | ~150MB |
| base | 中 | 速い | ~300MB |
| small | 高 | 普通 | ~500MB |
| medium | 最高 | 遅い | ~1.5GB |

日本語の場合、`small` 以上を推奨します。

---

## 開発

```bash
make install   # 依存関係のインストール
make test      # テストの実行
make lint      # リントの実行
make run       # 起動
```

Python から直接起動する場合は `python -m src.main` を使用します。

コントリビュートの前に `AGENTS.md` と `CONTRIBUTING.md` を読んでください。

---

## ライセンス

MIT
