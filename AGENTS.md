# AGENTS.md — VoicePaste エージェント作業規約

このファイルはLLMエージェント（Claude、Copilot等）がこのリポジトリで作業する際に従うべき規約を定める。人間の開発者も同様に従うこと。

## 仕様
`SPEC.md` を参照。
## 実装計画
`IMPLEMENTATION_PLAN.md`を参照
## README
`README.md` を参照

---

## 絶対に守ること

### コミットに関して

**LLMはコミットを行ってはならない。**

- `git commit` を実行しない
- `git push` を実行しない
- コミットメッセージを生成して自動コミットするスクリプトを作成しない
- コミットの代わりに、変更内容をサマリーとして人間に提示する

コミットは必ず人間が内容を確認した上で行う。

### ファイル削除に関して

**LLMは既存ファイルを削除してはならない。**

- `rm` / `del` / `os.remove` 等でファイルを削除しない
- ファイルを削除したい場合は、その旨を人間に提案する

### 設定ファイルに関して

**LLMは `config.yaml` のデフォルト値を変更してはならない。**

- 新しいキーの追加は可
- 既存キーの値変更は不可（人間の判断が必要）

---

## テストに関して

### テストを必ず書く

新しいモジュールや関数を実装した場合、対応するテストを `tests/` に作成すること。テストなしの実装PRは受け付けない。

### テストの構成

```
tests/
├── test_config.py
├── test_clipboard.py
├── test_formatter.py
├── test_recorder.py
├── test_transcriber.py
├── test_hotkey.py
└── test_main.py
```

### テストの書き方

外部依存（マイク・クリップボード・Whisperモデル・OSコマンド）は必ずモックする。

```python
# 良い例 : subprocess をモックしてクリップボードをテスト
from unittest.mock import patch

def test_copy_to_clipboard_macos():
    with patch("subprocess.run") as mock_run:
        copy_to_clipboard("テスト")
        mock_run.assert_called_once_with(
            "pbcopy", input=b"\xe3\x83\x86\xe3\x82\xb9\xe3\x83\x88"
        )
```

```python
# 悪い例 : 実際のクリップボードに書き込むテスト（CIで失敗する）
def test_copy_to_clipboard_bad():
    copy_to_clipboard("テスト")
    # 検証なし、副作用だけ
```

### テスト実行

```bash
make test
# または
pytest tests/ -v --cov=src
```

カバレッジは80%以上を維持すること。

---

## コードスタイル

### フォーマッタ・リンタ

`ruff` を使用する。

```bash
make lint
# または
ruff check src/ tests/
ruff format src/ tests/
```

### 型ヒント

全ての関数に型ヒントを付ける。

```python
# 良い例
def format(self, text: str) -> str:
    ...

# 悪い例
def format(self, text):
    ...
```

### docstring

公開インターフェース（クラス・パブリックメソッド）にはdocstringを書く。

```python
def copy_to_clipboard(text: str) -> None:
    """OSのクリップボードにテキストを書き込む。

    Args:
        text: クリップボードに書き込む文字列。

    Raises:
        RuntimeError: クリップボードへの書き込みに失敗した場合。
    """
```

---

## 実装手順

IMPLEMENTATION_PLAN.md のフェーズ順に実装すること。フェーズをスキップしない。

各フェーズの完了条件を満たしてから次のフェーズに進む。

---

## 変更提案の形式

LLMが変更を提案する場合、以下の形式でサマリーを出力すること。

```
## 変更サマリー

### 変更ファイル
- src/formatter.py : 新規作成
- tests/test_formatter.py : 新規作成

### 変更内容
- Formatterクラスを実装した
- フィラー除去・句読点補完のメソッドを追加した
- 対応するテストを追加した（カバレッジ: 92%）

### 未解決の問題
- なし

### 人間への確認事項
- フィラーリストのデフォルト値が適切か確認してほしい
```

---

## やってはいけないこと（チェックリスト）

- [ ] `git commit` を実行する
- [ ] `git push` を実行する
- [ ] 既存ファイルを削除する
- [ ] `config.yaml` のデフォルト値を変更する
- [ ] テストなしでモジュールを実装する
- [ ] 外部依存をモックせずにテストを書く
- [ ] 型ヒントを省略する
- [ ] IMPLEMENTATION_PLAN.md のフェーズ順を無視して実装する
- [ ] カバレッジを80%未満にする
