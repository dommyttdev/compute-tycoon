# ドキュメントガイド

このディレクトリは、目的別に文書を分離しています。

| 読みたい内容 | 文書 |
| --- | --- |
| システム全体と依存方向 | [アーキテクチャ概要](architecture/overview.md) |
| ゲーム状態と主要概念 | [ドメインモデル](design/domain-model.md) |
| 配線、IPv4、経路探索 | [ネットワーク設計](design/networking.md) |
| 負荷生成と資源競合 | [ワークロード実行](design/workload-execution.md) |
| CLIコマンド | [CLIリファレンス](reference/cli.md) |
| JSON設定とセーブ形式 | [データ・設定リファレンス](reference/data-and-configuration.md) |
| 静的検査と開発手順 | [品質保証](development/quality.md) |
| 設計判断の履歴 | [ADR](adr/README.md) |

エージェント向けの短いプロジェクト文脈はルートの `CONTEXT.md`、運用設定は
`docs/agents/` にあります。実装詳細を変更した場合は、対応する設計書と必要なADRを
同じ変更で更新してください。
