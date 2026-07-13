# ワークロード実行

## 生成

`WorkloadCatalog`は`hardware_sim/data/workloads.json`を読み込みます。各要求量は
`[最小値, 最大値]`から実行時に乱数で選ばれます。

- 単一ノード: `WorkloadProfile`から`WorkInfo`を生成
- 複数ノード: `InfrastructureWorkloadProfile`から順序付きStepを生成

要求は`ResourceRequirements`に格納され、CPU、Memory、Storage、GPU、Networkの
型付きRequirementとして取得されます。Executorは存在する要求だけを処理します。

役割ごとのRequirementとDevice操作の順序は`domain-model.md`のノード役割表に従います。
Network Requirementは受信と送信、Storage Requirementは読取と書込の各操作に対応し、
要求量がない操作は飛ばします。

## デバイス時間モデル

| デバイス | 所要時間・競合 |
| --- | --- |
| CPU | required clocks ÷ 割当Hz。必要コア数が空くまで待つ |
| Memory | 容量を一時確保。空き容量が不足すれば待つ |
| Storage | latency + amount ÷ speed。queue depthをSemaphoreで制限 |
| GPU | compute ÷ FLOPS。GPU memoryが空くまで待つ |
| NIC | latency + amount ÷ bandwidth。queue depthを制限 |

Memoryは処理終了時に解放され、Storage書き込み量は永続的な使用容量になります。
容量を超える要求は`ResourceCapacityError`です。Workが処理途中で失敗した場合も、Workが
一時的に確保したMemory、Deviceの実行枠、キュー深度などの資源は`finally`相当の経路で
必ず解放します。永続的なStorage書き込みなど、完了済み操作の効果は一時資源に含みません。
失敗したDevice操作以降の役割処理は実行しません。

## 複数ノード実行

ゲームはStepを直列に実行します。隣接StepのNodeが異なる場合はTopologyで経路を確認し、
両NodeのEventLogへ経路を記録します。各StepはNodeへ投入後`wait_all()`で完了を待ってから
次へ進みます。

## 観測

DeviceとNodeは不変Snapshotを返します。`HardwareMonitor`は別スレッドで周期取得し、
使用率、累積処理量、キュー、成功・失敗数を表示します。Snapshotは保存データではなく
実行中状態の観測用です。
