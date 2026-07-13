# Architecture Decision Records

ADRは、実装から読み取れる重要な設計判断と、その理由・影響を日本語で残します。

## 命名と状態

- ファイル名: `NNNN-kebab-case.md`
- 本文: 日本語
- 状態: `提案`、`採用`、`非推奨`、`置換済み`
- 採用済みADRは書き換えず、判断変更時は新しいADRから置換元を参照する

## 一覧

- [ADR-0001: カタログ駆動のノード組み立て](0001-catalog-driven-node-assembly.md)
- [ADR-0002: 不変なネットワークトポロジー](0002-immutable-network-topology.md)
- [ADR-0003: ノード役割と実行戦略の分離](0003-role-based-execution.md)
- [ADR-0004: 状態バージョン監視による自動保存](0004-versioned-autosave.md)
- [ADR-0005: 保存データの検証とトランザクショナルな復元](0005-transactional-save-load.md)
- [ADR-0006: ノード役割変更の同期境界](0006-node-role-change-synchronization.md)
