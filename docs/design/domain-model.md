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

| 役割 | RequirementとDevice処理の順序 |
| --- | --- |
| `unassigned` | 実行不可 |
| `application_server` | Network受信→Memory確保→Storage読取→CPU処理→Storage書込→Network送信 |
| `database_server` | Network受信→Memory確保→Storage読取→CPU処理→Storage書込→Network送信 |
| `storage_server` | Network受信→Storage読取→Storage書込→Network送信 |
| `network_switch` | Network受信→Network送信 |
| `router` | Network受信→CPU処理→Network送信 |
| `gpu_worker` | Memory確保→Storage読取→GPU処理→CPU処理→Storage書込 |

ExecutorはWorkに存在するRequirementだけを上表の順序で処理します。同じNetwork
Requirementを受信と送信に、同じStorage Requirementの読取量と書込量をそれぞれの
Device操作に対応させます。要求量がない操作は実行しません。

役割変更はNodeの役割とExecutor、および保存用BuildRequestを同時に更新します。

## ライフサイクル

Nodeは生成時にワーカースレッドを開始します。投入されたWorkは
queued→running→completedまたはfailedへ進み、終端状態から別の状態へは遷移しません。
Device処理が失敗した場合は残りの処理を行わずfailedになります。

Workは投入を受け付けた順にキューへ入り、ワーカーはその順に取り出します。ワーカーが
1つなら実行開始順もFIFOになります。複数ワーカーでは完了順を保証しません。

`wait_all()`はキューと実行中集合の両方が空になったときだけ戻ります。`stop()`は呼出し前に
受け付けたキュー内および実行中のWorkを処理し終えてから同期的に戻ります。複数回呼び出しても
同じ停止状態を保ちます。`stop()`が戻った後の新規Work投入は、キュー、実行中集合、成功数、
失敗数を変更せず拒否します。
