# ドメインモデル

## ゲーム状態

`ComputeTycoonGame`は1セッションの集約ルートです。以下を所有します。

- 購入済み資産を表す`Inventory`
- 構築済み`Node`と、その復元に必要な`BuildRequest`
- 現在の`NetworkTopology`
- `PartsCatalog`と`WorkloadCatalog`
- `EventLog`、状態バージョン、自動保存ワーカー

状態変更はゲームの`RLock`内で行い、成功後に`state_version`を増やします。

## 購入・消費・構築

完成品サーバー、部品、ケーブルは購入時にInventoryへ追加されます。完成品配置では
該当役割の在庫を1つ消費します。手動組み立てでは要求部品を検査した後、すべてを
まとめて消費します。ケーブルは接続時に消費し、切断時に戻します。

手動組み立ては次の順序です。

1. `BuildRequest`を作成する。
2. Inventoryの数量を確認する。
3. `NodeBuilder.validate()`で互換性を検査する。
4. カタログ上の構成値から実行時Deviceを作る。
5. `Node`を登録し、Topologyのノード集合を更新する。
6. Inventoryを消費し、イベントと状態変更を記録する。

## 組み立て制約

- CPUソケット型と個数
- メモリ規格、スロット数、1枚/合計容量、ECC対応
- ストレージコネクタ型と個数
- GPU・拡張NICのPCIe世代とレーン数
- CPU、メモリ、ストレージを最低1つずつ搭載

複数部品は、CPUコア数・メモリ容量・ストレージ容量/速度を合算します。CPU周波数と
ストレージ遅延は最も遅い・小さい値を採用します。

## ノード役割

`NodeRole`はExecutorを選択します。

| 役割 | 主な処理 |
| --- | --- |
| `unassigned` | 実行不可 |
| `application_server` | NIC受信→RAM→Storage→CPU→Storage→NIC送信 |
| `database_server` | Application Serverと同じ資源順序 |
| `storage_server` | NIC受信→Storage読書き→NIC送信 |
| `network_switch` | NIC受信→NIC送信 |
| `router` | NIC受信→CPU→NIC送信 |
| `gpu_worker` | RAM→Storage→GPU→CPU→Storage |

役割変更はNodeの役割とExecutor、および保存用BuildRequestを同時に更新します。

## ライフサイクル

Nodeは生成時にワーカースレッドを開始します。投入されたWorkは
queued→running→completedまたはfailedへ進みます。`wait_all()`はキューと実行中集合が
空になるまで待機し、`stop()`後は新規Workを拒否して既存キューを処理後に終了します。
