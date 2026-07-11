# アーキテクチャ概要

## 境界と依存方向

システムは、CLI、ゲーム調整、ドメインモデル、デバイスシミュレーション、
データ読み込みの順に依存します。下位層はCLIを知りません。

```text
main.py / hardware.py
        |
        v
shell.py  --->  game.py
                    |
        +-----------+-----------+
        v           v           v
   assembly.py  networking.py  workloads.py
        |           |           |
        +-------> node.py <------+
                    |
                    v
          executors.py / devices/

catalog.py / config.py ---> JSON data
game.py ---> events.py / persistence.py
node.py ---> snapshots.py ---> monitor.py
```

## 実行入口

- `main.py`: `python main.py` のCLI入口。加えて、コード駆動の連続シミュレーション用
  `main()` と既定構成の生成関数を持つ。
- `hardware.py`: `hardware_sim` の主要型を再公開する互換・利便API。
- `hardware_sim/__init__.py`: パッケージ公開API。

## 主要コンポーネント

| コンポーネント | 責務 |
| --- | --- |
| `TycoonShell` | 入力解析と表示。ゲーム規則を保持しない |
| `ComputeTycoonGame` | インベントリ、ノード、ネットワーク、実行、保存を調整 |
| `NodeBuilder` | カタログ参照、互換性検証、実行時デバイス生成 |
| `Node` | ワーカー・キュー・成功/失敗状態を所有 |
| `RoleExecutor` | 役割ごとにデバイス処理順序を決定 |
| `NetworkTopology` | 物理接続、IPv4アドレス、経路表から到達性を解決 |
| `WorkloadCatalog` | JSONプロファイルから要求量をサンプリング |
| `HardwareMonitor` | 不変スナップショットを周期表示 |
| `AutosaveWorker` | 状態バージョンを監視して原子的にJSON保存 |

## 並行処理

各`Node`はCPU並列度または明示した`workers`数のデーモンスレッドを起動します。
ワークはFIFOキューから取り出され、役割Executorを通してデバイスへ渡されます。
CPUとメモリは`Condition`、ストレージとNICはキュー深度付きSemaphore、GPUは
`Condition`で競合を表現します。ゲーム状態は`RLock`、ログとデバイス統計は個別の
Lockで保護されます。

## 二つの実行モデル

現在は互換性のため二つのモデルがあります。

- プレイ用: `ComputeTycoonGame` + `Node` + `NetworkTopology`。
- コード駆動: `HardwareModule` または静的な`Infrastructure`。

新しいゲーム機能は前者へ追加します。`Infrastructure.links`は静的構成のメタデータで、
プレイ用の経路解決には使われません。
