# 品質保証

## 環境

Python 3.14以上を使用します。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 品質チェック

```powershell
.\.venv\Scripts\python.exe scripts\run_static_tests.py
```

スクリプトは順に以下を実行します。

1. `compileall`: 構文とbytecode生成
2. `ruff check`: Lintとimport順序
3. `ruff format --check`: format差分
4. `mypy`: 段階的な型検査
5. `coverage run -m pytest`: Assembly、Inventoryなどの動作契約テストと
   line・branch coverageの計測
6. `coverage report`: 未実行行を表示し、対象全体のカバレッジが74.0%を
   下回っていないことを確認

設定は`pyproject.toml`、開発依存は`requirements-dev.txt`が正です。現在のmypy設定は
動的JSONと一部の実行時objectを許容する移行用baselineです。

カバレッジ対象は`hardware_sim`、`main.py`、`hardware.py`です。74.0%は文書化された
重要契約のgap分析後に得たline・branch coverageの実測値を整数へ切り下げた回帰検出用
baselineです。総率だけを上げるテストは追加せず、テスト追加後の実測値に合わせて
引き上げます。分析結果と除外理由は`test-coverage.md`を参照してください。

## 変更時の確認観点

- 組み立て規則: CatalogとNodeBuilderの制約が一致すること
- 並行処理: 例外時にもMemory・Device状態が解放されること
- ネットワーク: 物理接続とIP経路を混同しないこと
- 保存: 新しいゲーム状態を追加したらsave/loadを対で更新すること
- 公開API: `hardware_sim/__init__.py`と`hardware.py`の再公開を確認すること
- 文書: 振る舞い変更に対応する設計書とADRを更新すること
