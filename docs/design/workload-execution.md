# ワークロード実行

## 生成

`WorkloadCatalog`は`hardware_sim/data/workloads.json`を読み込みます。各要求量は
`[最小値, 最大値]`から実行時に乱数で選ばれます。

- 単一ノード: `WorkloadProfile`から`WorkInfo`を生成
- 複数ノード: `InfrastructureWorkloadProfile`から順序付きStepを生成

要求は`ResourceRequirements`に格納され、CPU、Memory、Storage、GPU、Networkの
型付きRequirementとして取得されます。Executorは存在する要求だけを処理します。

## デバイス時間モデル

| デバイス | 所要時間・競合 |
| --- | --- |
| CPU | required clocks ÷ 割当Hz。必要コア数が空くまで待つ |
| Memory | 容量を一時確保。空き容量が不足すれば待つ |
| Storage | latency + amount ÷ speed。queue depthをSemaphoreで制限 |
| GPU | compute ÷ FLOPS。GPU memoryが空くまで待つ |
| NIC | latency + amount ÷ bandwidth。queue depthを制限 |

Memoryは処理終了時に解放され、Storage書き込み量は永続的な使用容量になります。
容量を超える要求は`ResourceCapacityError`です。

## 複数ノード実行

ゲームはStepを直列に実行します。隣接StepのNodeが異なる場合はTopologyで経路を確認し、
両NodeのEventLogへ経路を記録します。各StepはNodeへ投入後`wait_all()`で完了を待ってから
次へ進みます。

## 観測

DeviceとNodeは不変Snapshotを返します。`HardwareMonitor`は別スレッドで周期取得し、
使用率、累積処理量、キュー、成功・失敗数を表示します。Snapshotは保存データではなく
実行中状態の観測用です。
