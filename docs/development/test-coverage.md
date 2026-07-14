# テストカバレッジ方針

## 基本方針

カバレッジは未検証契約を発見するための補助指標として使います。`CONTEXT.md`、設計文書、
ADRを仕様の正とし、公開インターフェースと実collaboratorから観測できる振る舞いを検証します。
private実装、単純なpropertyや表示分岐を総率だけのためにテストしません。

## 2026-07-14 gap matrix

| 仕様上の契約 | 既存の保護 | 判定 | 対応 |
| --- | --- | --- | --- |
| TargetはIP addressを持つ | direct/routed経路はIP設定済みの正常系のみ | 未検証 | IP未設定Targetの拒否とTopology不変性を追加 |
| 明示Route interfaceは実在する | 正常な`lan0`の追加のみ | 未検証 | 未知interfaceの拒否と元Topology不変性を追加 |
| Gatewayは既知かつsource subnetからL2到達可能 | 未知Gatewayとrouteなしは検証済み | 一部未検証 | 既知だがsource subnet外のGateway拒否を追加 |
| 複数delegationは順番に実行し、失敗後は残りとpostを行わない | 単一delegationの成功・失敗と複数Job順序は検証済み | 未検証 | 2番目の子失敗後に残りの子とpostを省略する契約を追加 |
| `wait_for(work)`は無関係なWorkを待たない | 単一Workの成功・失敗待機のみ | 未検証 | 無関係なWorkがrunning中でも対象結果を返す契約を追加 |
| 後段Device失敗時に一時資源を解放する | 失敗直後の使用量ゼロは検証済み | 一部未検証 | 次のWorkが同じMemory/CPU capacityを再利用できることへ強化 |
| Node IDはGame内で一意 | 完成品Nodeの重複配置は検証済み | 経路別に未検証 | `build_node()`の重複拒否でparts、Topology、versionが不変なことを追加 |

## 追加しなかった領域

- transactional save/load、復元失敗時のworker停止、原子的save置換は既存のPersistence契約テストで保護されています。
- Assembly互換性、Inventory rollback、Topology immutability、停止済みNode、Role変更、公開API再公開は既存契約と同値なケースを追加しません。
- `shell.py`と`main.py`の網羅的な表示・error message分岐は、CLI境界の既存契約を超えて総率だけを上げるため対象外です。
- `HardwareModule`と静的`Infrastructure`は互換用のコード駆動モデルです。文書化された新しいリスクがない限り、プレイ用Gameの契約より優先しません。
- `HardwareMonitor`の単純な周期表示は既存の開始・停止・表示契約を維持し、内部ループの行到達を目的に追加しません。

## baselineの更新

リスク由来テストを追加した後、標準品質スクリプトでline・branch coverageを再計測します。
`fail_under`は実測値を超えない整数へ切り下げます。表示上の丸め値ではなく、
`coverage report --format=total --precision=6`の値を確認します。

今回の再計測結果は次のとおりです。

| 指標 | 変更前 | 変更後 |
| --- | ---: | ---: |
| tests | 155 | 161 |
| line・branch coverage | 74.493813% | 74.606299%–74.662542% |
| missed statements | 643 | 640–641 |
| partial branches | 124 | 121–122 |

変更後の値は標準品質スクリプトを連続実行した範囲で、並行処理の分岐取得タイミングにより
変動します。`fail_under`は最低実測値を整数へ切り下げた74.0%とします。総率の増分が
小さいのは、既存の正常経路を再利用して未検証の拒否・順序・cleanup契約を追加したためです。
