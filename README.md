# Compute Tycoon

ハードウェア構成、サーバー役割、ネットワーク、ワークロード実行を扱う
Python製のCLIシミュレーションです。プレイヤーは部品や完成品を購入し、ノードを
組み立て、配線・IPアドレス・経路を設定して、計算資源への負荷を観察します。

## 実行

Python 3.14以上が必要です。

```powershell
python main.py
```

起動すると `compute-tycoon>` プロンプトが表示されます。基本操作は
[CLIリファレンス](docs/reference/cli.md)を参照してください。

## ドキュメント

文書体系の入口は[docs/README.md](docs/README.md)です。システム全体を把握する場合は
[アーキテクチャ概要](docs/architecture/overview.md)から読み始めてください。

## 開発時の検証

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\run_static_tests.py
```

詳細は[品質保証](docs/development/quality.md)を参照してください。
