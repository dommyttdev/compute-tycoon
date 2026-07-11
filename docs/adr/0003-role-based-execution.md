# ADR-0003: ノード役割と実行戦略の分離

- 状態: 採用
- 日付: 2026-07-11

## 文脈

同じ物理Device構成でも、Application Server、Router、GPU Workerでは使用する資源と順序が
異なる。Node本体へ役割分岐を集約するとキュー管理と処理規則が密結合になる。

## 決定

Nodeはキューとライフサイクルを所有し、役割ごとの処理順序は`RoleExecutor`実装へ委譲する。
役割変更時はExecutorを差し替える。

## 結果

役割追加はExecutor追加として局所化できる。一方、NodeRole、Executorの対応表、保存形式、
Shopの完成品定義を一貫して更新する必要がある。
